
from ethpwn.ethlib.evm.plugins.base import BaseAnalysisPlugin
from ethpwn.ethlib.evm.plugins.utils import *

from typing import NamedTuple


class CheckPlugin(BaseAnalysisPlugin):

    name = "jackal_pfv_checker"

    def __init__(self, calltacid):
        super().__init__()
        self.calltacid = calltacid
        self.call_is_reachable = False

    def pre_opcode_hook(self, opcode, computation):
        pc = hex(computation.code.program_counter-1)
        if opcode.mnemonic == 'CALL':
            print(opcode.mnemonic)
        if opcode.mnemonic == 'CALL' and pc == self.calltacid:
            self.call_is_reachable = True




