# -*- coding: utf-8 -*-
# from odoo import http


# class Odoo-module-template(http.Controller):
#     @http.route('/odoo-module-template/odoo-module-template', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/odoo-module-template/odoo-module-template/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('odoo-module-template.listing', {
#             'root': '/odoo-module-template/odoo-module-template',
#             'objects': http.request.env['odoo-module-template.odoo-module-template'].search([]),
#         })

#     @http.route('/odoo-module-template/odoo-module-template/objects/<model("odoo-module-template.odoo-module-template"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('odoo-module-template.object', {
#             'object': obj
#         })

