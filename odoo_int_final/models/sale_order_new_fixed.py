from odoo import models, fields
from .ceretax_document_mixin import CeretaxDocumentMixin


class SaleOrder(models.Model, CeretaxDocumentMixin):
    _inherit = ["sale.order"]

    def _ceretax_get_lines(self):
        return self.order_line

    def _ceretax_get_partner(self):
        return self.partner_shipping_id

    def _ceretax_get_document_name(self):
        return self.name

    def _ceretax_get_document_total(self):
        return self.amount_untaxed

    def _ceretax_get_document_date(self):
        return fields.Date.to_string(self.date_order or fields.Date.today())
