import requests
from odoo import models, fields, api


class CeretaxPsCode(models.Model):
    _name = "ceretax.ps.code"
    _description = "Ceretax PS Code Lookup"
    _rec_name = "ps_code"

    # Fields
    ps_code = fields.Char(required=True)
    description = fields.Char(required=True)

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        readonly=True,
    )

    # Display name for smart search
    @api.depends("ps_code", "description")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.ps_code} - {rec.description}"

    # How records appear in dropdown
    def name_get(self):
        result = []
        for rec in self:
            label = f"{rec.ps_code} - {rec.description}"
            result.append((rec.id, label))
        return result

    def name_get(self):
        res = []
        for rec in self:
            code = rec.ps_code or ''
            desc = rec.description or ''
            res.append((rec.id, f"{code} - {desc}"))
        return res




    # API loader
    @api.model
    def load_from_api(self):
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param("ceretax.api_key", "")
        if not key:
            return

        url = "https://data.cert.ceretax.net/psCodes"
        headers = {
            "accept": "application/json",
            "x-api-key": key
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return

        for item in data:
            rec = self.search([("ps_code", "=", item["psCode"])], limit=1)
            if rec:
                rec.write({"description": item["psCodeDescription"]})
            else:
                self.create({
                    "ps_code": item["psCode"],
                    "description": item["psCodeDescription"],
                })

class ProductProduct(models.Model):
    _inherit = "product.product"

    ceretax_ps_code_id = fields.Many2one(
        "ceretax.ps.code",
        string="PS Code",
        help="Searchable list of PS Codes",
    )

    ceretax_ps_code = fields.Char(
        related="ceretax_ps_code_id.ps_code",
        store=True,
        readonly=True,
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ceretax_ps_code_id = fields.Many2one(
        "ceretax.ps.code",
        related="product_variant_id.ceretax_ps_code_id",
        readonly=False,
        store=True,
    )
    ceretax_ps_code = fields.Char(
        related="ceretax_ps_code_id.ps_code",
        store=True,
        readonly=True,
    )


class CeretaxCategory(models.Model):
    _inherit = "product.category"

    ceretax_ps_code_id = fields.Many2one(
        "ceretax.ps.code",
        string="PS Code",
        help="Searchable list of PS Codes for categories",
    )

    ps_code = fields.Char(
        related="ceretax_ps_code_id.ps_code",
        store=True,
        readonly=True,
    )
