from odoo import models, fields

class AccountMoveLineTax(models.Model):
    _name = "account.move.line.tax"
    _description = "CereTax - Account Move Line Tax"
    _order = "id desc"

    move_line_id = fields.Many2one('account.move.line', string='Move Line', ondelete='cascade', required=True)
    description = fields.Char()
    tax_authority = fields.Char()
    tax_level = fields.Char()
    tax_type = fields.Char()
    tax_class = fields.Char()
    rate = fields.Float()
    taxable = fields.Char()
    tax_type_ref_desc = fields.Char()
    exempt_amount = fields.Char()
    percent_taxable = fields.Char()
    non_taxable_amount = fields.Char()
    calc_base = fields.Monetary(currency_field='currency_id')
    total_tax = fields.Monetary(currency_field='currency_id')
    geocode = fields.Char()
    extra = fields.Text()
    currency_id = fields.Many2one('res.currency', related='move_line_id.move_id.currency_id', store=True, readonly=True)
