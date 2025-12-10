
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)

class OdooIntController(http.Controller):

    @http.route('/odoo_int_final/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def webhook(self, **payload):
        # simple webhook handler: create transaction log and return ok
        try:
            tx = request.env['odoo.int.transaction'].sudo().create({
                'model': 'webhook',
                'request': str(payload),
                'state': 'done',
                'response': 'received'
            })
            return {'status': 'ok', 'tx': tx.name}
        except Exception as e:
            _logger.exception('Webhook processing failed')
            return {'status': 'error', 'error': str(e)}
