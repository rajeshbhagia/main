# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests

class ProductTemplate(models.Model):
    _inherit = "product.template"

    ceretax_ps_code = fields.Selection(
        selection="_get_ps_codes",   # SAFE: no API call during registry load
        string="PS Code",
    )

    @api.model
    def _get_ps_codes(self):
        """Load PS codes safely during UI field rendering and not during module load."""
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param("ceretax.api_key", "")

        if not key:
            return []  # Do NOT block Odoo

        url = "https://data.cert.ceretax.net/psCodes"
        headers = {
            "accept": "application/json",
            "x-api-key": key
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            return [
                (c["psCode"], f"{c['psCode']} - {c['psCodeDescription']}")
                for c in data
            ]
        except Exception:
            return []


# class ProductProduct(models.Model):
#     _inherit = "product.product"

#     ceretax_ps_code = fields.Selection(
#         selection="_get_ps_codes", 
#         string="PS Code",
#     )

#     @api.model
#     def _get_ps_codes(self):
#         """Load PS codes safely during UI field rendering and not during module load."""
#         icp = self.env['ir.config_parameter'].sudo()
#         key = icp.get_param("ceretax.api_key", "")

#         if not key:
#             return []  # Do NOT block Odoo

#         url = "https://data.cert.ceretax.net/psCodes"
#         headers = {
#             "accept": "application/json",
#             "x-api-key": key
#         }

#         try:
#             response = requests.get(url, headers=headers, timeout=10)
#             response.raise_for_status()
#             data = response.json()

#             return [
#                 (c["psCode"], f"{c['psCode']} - {c['psCodeDescription']}")
#                 for c in data
#             ]
#         except Exception:
#             return []


class CeretaxCategory(models.Model):
    _inherit = "product.category"

    ps_code = fields.Selection(
        selection="_get_ps_codes",   # SAFE: no API call during registry load
        string="PS Code",
    )

    @api.model
    def _get_ps_codes(self):
        """Load PS codes safely during UI field rendering and not during module load."""
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param("ceretax.api_key", "")

        if not key:
            return []  # Do NOT block Odoo

        url = "https://data.cert.ceretax.net/psCodes"
        headers = {
            "accept": "application/json",
            "x-api-key": key
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            return [
                (c["psCode"], f"{c['psCode']} - {c['psCodeDescription']}")
                for c in data
            ]
        except Exception:
            return []
