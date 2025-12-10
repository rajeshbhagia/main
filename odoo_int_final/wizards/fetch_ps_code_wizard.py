# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class CeretaxFetchPSCodeWizard(models.TransientModel):
    _name = 'ceretax.fetch.pscode.wizard'
    _description = 'Fetch PS Codes from CereTax'

    info = fields.Text(string='Info', readonly=True)

    def action_fetch(self):
        ps_model = self.env['ceretax.ps.code']
        res = ps_model.load_from_api()
        if not res:
            self.info = 'No response from API (check logs and API key)'
        elif res.get('error'):
            self.info = 'Error: %s' % res.get('error')
        else:
            self.info = 'Success: fetched %s codes' % res.get('fetched', 0)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
