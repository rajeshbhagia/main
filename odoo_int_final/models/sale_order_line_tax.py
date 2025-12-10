from odoo import models, fields

class SaleOrderLineTax(models.Model):
    _name = "sale.order.line.tax"
    _description = "CereTax Line Tax"

    sale_line_id = fields.Many2one("sale.order.line", ondelete="cascade")

    description = fields.Char()
    tax_authority = fields.Char()
    tax_level = fields.Char()
    tax_type = fields.Char()
    tax_class = fields.Char()
    tax_type_ref_desc = fields.Char()
    exempt_amount = fields.Char()
    percent_taxable = fields.Char()
    non_taxable_amount = fields.Char()
    taxable = fields.Char()
    rate = fields.Float()
    calc_base = fields.Monetary(currency_field="currency_id")
    total_tax = fields.Monetary(currency_field="currency_id")

    geocode = fields.Char()
    extra = fields.Text()

    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id.id)
