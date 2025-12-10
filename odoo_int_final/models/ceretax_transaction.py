
from odoo import models, fields

class CeretaxTransaction(models.Model):
    _name="ceretax.transaction"
    _description="CereTax Log"

    endpoint=fields.Char()
    request_headers=fields.Text()
    request_body=fields.Text()
    response_body=fields.Text()
    status_code=fields.Integer()
    name = fields.Char(string="Transaction Name", required=True)
    request_payload = fields.Text()
    response_payload = fields.Text()
    status = fields.Char()
    partner_id = fields.Many2one("res.partner")
    sale_order_id = fields.Many2one("sale.order")
    sale_line_id = fields.Many2one("sale.order.line")
    timestamp = fields.Datetime(default=lambda self: fields.Datetime.now())
