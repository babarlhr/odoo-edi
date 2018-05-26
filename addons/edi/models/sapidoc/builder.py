"""IDoc Document Model Builder

Construct a SAP IDoc document model from a syntax description (as
generated by SAP transaction WE63).
"""

from collections import defaultdict
from .model import Record, IDoc
from .lexer import lexer
from .parser import parser


def subtree_walk(subtree):
    """Walk segment branches of abstract syntax tree"""
    for branch in subtree:
        if hasattr(branch, 'segments'):
            for subbranch in subtree_walk(branch.segments):
                yield subbranch
        else:
            yield branch


class Model(object):

    __slots__ = ['tree', 'doc']

    @classmethod
    def parse(cls, description):
        """Construct document model from syntax description"""
        return cls(parser.parse(description, lexer=lexer))

    def _record(self, name, base, subtree):
        """Construct record class from abstract syntax subtree"""
        ns = {x.name: x.type(slice(x.character_first - 1, x.character_last))
              for x in subtree.fields}
        ns['__slots__'] = []
        name = ('%s.%s' % (self.tree.segments.idoc.name, name))
        return type(name, (base,), ns)

    def __init__(self, tree):
        """Construct document model from abstract syntax tree"""
        self.tree = tree
        ControlRecord = self._record('Control', Record, tree.records.control)
        DataRecord = self._record('Data', Record, tree.records.data)
        DataRecords = defaultdict(lambda: DataRecord)
        for branch in subtree_walk(tree.segments.idoc.segments):
            name = branch.name
            DataRecords[name] = self._record(name, DataRecord, branch)
        ns = {
            '__slots__': [],
            'ControlRecord': ControlRecord,
            'DataRecord': DataRecord,
            'DataRecords': DataRecords,
            }
        self.doc = type(self.tree.segments.idoc.name, (IDoc,), ns)

    def __call__(self, raw):
        """Parse document using corresponding document model"""
        return self.doc(raw)
