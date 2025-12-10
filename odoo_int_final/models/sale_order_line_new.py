# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # A fields
    ceretax_line_tax = fields.Monetary(currency_field="currency_id", string="CereTax Line Tax")
    ceretax_tax_details = fields.Text(string="CereTax Tax Details")
    ceretax_line_id = fields.Char(string="CereTax Line ID")

    # From B
    ceretax_line_response = fields.Text(string="CereTax Raw Line JSON")
    tax_line_ids = fields.One2many("sale.order.line.tax", "sale_line_id", string="Tax Lines", copy=False)

    # -----------------------------
    # A: override compute totals
    # -----------------------------
    @api.depends('price_subtotal', 'ceretax_line_tax', 'currency_id')
    def _compute_amount(self):
        super(SaleOrderLine, self)._compute_amount()
        for line in self:
            currency = line.currency_id or line.order_id.currency_id
            subtotal = line.price_subtotal or 0.0
            tax = line.ceretax_line_tax or 0.0

            if currency:
                subtotal = currency.round(subtotal)
                tax = currency.round(tax)

            line.price_tax = tax
            line.price_total = subtotal + tax

    # -----------------------------
    # B: tax-line extraction
    # -----------------------------
    def action_sync_ceretax_to_tax_lines(self):
        Tax = self.env["sale.order.line.tax"]

        for line in self:
            Tax.search([("sale_line_id", "=", line.id)]).unlink()

            if not line.ceretax_line_response:
                continue

            try:
                payload = json.loads(line.ceretax_line_response)
            except Exception:
                continue

            taxes = payload.get("taxes") or []

            to_create = []
            for t in taxes:
                geocode = t.get("geocode", "")
                if isinstance(geocode, dict):
                    geocode = geocode.get("geocode", "")

                to_create.append({
                    "sale_line_id": line.id,
                    "description": t.get("description") or t.get("taxTypeDesc") or "",
                    "tax_authority": t.get("taxAuthorityName") or t.get("taxAuthorityId"),
                    "tax_level": t.get("taxLevelDesc") or t.get("taxLevel"),
                    "tax_type": t.get("taxTypeDesc") or t.get("taxType"),
                    "tax_class": t.get("taxTypeClassDesc") or t.get("taxTypeClass"),
                    "rate": t.get("rate") or 0.0,
                    "calc_base": t.get("calculationBaseAmt") or t.get("originalCalcBase") or 0.0,
                    "total_tax": t.get("totalTax") or t.get("tax") or 0.0,
                    "geocode": geocode,
                    "extra": json.dumps(t),
                })

            if to_create:
                Tax.create(to_create)

    def write(self, vals):
        res = super().write(vals)
        if vals.get("ceretax_line_response"):
            self.action_sync_ceretax_to_tax_lines()
        return res
