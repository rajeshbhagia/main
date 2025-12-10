# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class CeretaxPSCode(models.Model):
    _name = 'ceretax.ps.code'
    _description = 'CereTax PS Codes'
    _rec_name = 'ps_code'

    ps_code = fields.Char(string='PS Code', required=True, index=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    @api.model
    def load_from_api(self):
        """Fetch PS codes from external API and update/create records.
        Only differences are applied: new codes are created, existing ones updated,
        and codes not present in feed are deactivated.
        """
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param('ceretax.api_key', '')
        if not key:
            _logger.warning('ceretax: API key not configured (ir.config_parameter ceretax.api_key)')
            return {'warning': 'API key not found'}

        url = 'https://data.cert.ceretax.net/psCodes'
        headers = {
            'accept': 'application/json',
            'x-api-key': key
        }

        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            _logger.exception('ceretax: failed to fetch PS codes: %s', e)
            return {'error': 'Failed to fetch from API'}

        incoming_codes = set()
        for item in data:
            code = item.get('psCode')
            desc = item.get('psCodeDescription') or ''
            if not code:
                continue
            incoming_codes.add(code)
            rec = self.search([('ps_code', '=', code)], limit=1)
            vals = {'description': desc, 'active': True}
            if rec:
                # update only if changed
                if rec.description != desc or not rec.active:
                    rec.write(vals)
            else:
                try:
                    self.create({'ps_code': code, 'description': desc, 'active': True})
                except Exception:
                    _logger.exception('ceretax: failed to create ps.code %s', code)

        # deactivate codes not present anymore
        to_deactivate = self.search([('ps_code', 'not in', list(incoming_codes)), ('active', '=', True)])
        if to_deactivate:
            try:
                to_deactivate.write({'active': False})
            except Exception:
                _logger.exception('ceretax: failed to deactivate old ps.codes')

        return {'success': True, 'fetched': len(incoming_codes)}
