"""EDI stock transfer request tutorial

This example shows the code required to implement a simple EDI pick
request document format comprising a CSV file with a fixed list of
columns:

* Product code
* Quantity

The picking type will be deduced from the filename by matching against
the sequence prefixes defined for each avaiable picking type.  For
example: a picking type with a prefix "WH/OUT/" will match filenames
starting with "OUT".
"""

import csv
import pathlib
import re
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class EdiDocument(models.Model):
    """Extend ``edi.document`` to include stock transfer tutorial records"""

    _inherit = 'edi.document'

    pick_request_tutorial_ids = fields.One2many(
        'edi.pick.request.tutorial.record', 'doc_id',
        string="Stock Transfer Requests",
    )
    move_request_tutorial_ids = fields.One2many(
        'edi.move.request.tutorial.record', 'doc_id',
        string="Stock Move Requests",
    )

    @api.multi
    @api.depends('pick_request_tutorial_ids',
                 'pick_request_tutorial_ids.pick_id')
    def _compute_pick_ids(self):
        super()._compute_pick_ids()
        for doc in self:
            doc.pick_ids += doc.mapped('pick_request_tutorial_ids.pick_id')


class EdiPickRequestTutorialRecord(models.Model):
    """EDI stock transfer request tutorial record

    This subclass may be omitted if no extra functionality is required
    beyond that provided by the base ``edi.pick.request.record``.
    """

    _name = 'edi.pick.request.tutorial.record'
    _inherit = 'edi.pick.request.record'
    _description = "Stock Transfer Request"


class EdiMoveRequestTutorialRecord(models.Model):
    """EDI stock move request tutorial record

    This subclass may be omitted if no extra functionality is required
    beyond that required by the base ``edi.move.request.record``.
    """

    _name = 'edi.move.request.tutorial.record'
    _inherit = 'edi.move.request.record'
    _description = "Stock Move Request"

    pick_request_id = fields.Many2one('edi.pick.request.tutorial.record')


class EdiPickRequestTutorialDocument(models.AbstractModel):
    """EDI stock transfer request tutorial document model"""

    _name = 'edi.pick.request.tutorial.document'
    _inherit = ['edi.move.tracker.document', 'edi.pick.request.document']
    _description = "Tutorial stock transfer request CSV file"""

    @api.model
    def pick_types_map(self, doc):
        """Construct a mapping from filenames to picking types

        Construct a mapping from input filenames to picking types,
        using the sequence prefix defined for each associated picking
        type.

        For example: the filename "OUT_TEST.CSV" will be mapped to the
        picking type with sequence prefix "WH/OUT/".
        """
        prefix_test = lambda prefix: re.compile(
            r'%s[\W\d_]' % next(x for x in reversed(prefix.split('/')) if x),
            flags=re.IGNORECASE
        )
        return [
            (prefix_test(x.sequence_id.prefix), x)
            for x in doc.doc_type_id.pick_type_ids if x.sequence_id.prefix
        ]

    @api.model
    def prepare(self, doc):
        """Prepare document"""
        # pylint: disable=too-many-locals
        super().prepare(doc)
        EdiPickRequestRecord = self.pick_request_record_model(doc)
        EdiMoveRequestRecord = self.move_request_record_model(doc)
        EdiMoveTrackerRecord = self.move_tracker_record_model(doc)
        PickingType = self.env['stock.picking.type']
        pick_type_map = self.pick_types_map(doc)

        # Create picking for each input attachment
        for fname, data in doc.inputs():

            # Look up picking type based on filename
            pick_type = PickingType.union(*(v for k, v in pick_type_map
                                            if k.match(fname)))
            if not pick_type:
                raise UserError(_("\"%s\" matches no picking types") % fname)
            if len(pick_type) > 1:
                raise UserError(_("\"%s\" matches multiple picking types: %s") %
                                (fname, ", ".join(pick_type.mapped('name'))))

            # Construct base name for this stock transfer
            name = pathlib.Path(fname).stem

            # Create stock transfer request
            EdiPickRequestRecord.create({
                'doc_id': doc.id,
                'name': name,
                'pick_type_id': pick_type.id,
            })

            # Create a single tracking identity
            EdiMoveTrackerRecord.create({
                'doc_id': doc.id,
                'name': name,
            })

            # Create stock moves
            reader = csv.reader(data.decode().splitlines())
            for line, (product, qty) in enumerate(reader, start=1):
                EdiMoveRequestRecord.create({
                    'doc_id': doc.id,
                    'pick_key': name,
                    'name': "%04d" % line,
                    'tracker_key': name,
                    'product_key': product,
                    'qty': float(qty),
                })
