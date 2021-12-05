import jex

# tkinter related libs
if jex.isPython3():
    import tkinter as tk
    from tkinter import ttk
    import tkinter.messagebox as tkMessageBox
    import tkinter.filedialog as tkFileDialog
    import tkinter.font as tkFont
else:
    import Tkinter as tk
    import ttk
    import tkFileDialog
    import tkFont


if jex.isPython3():
    from enum import Enum
    from typing import List

# common libs
import re


class ArrowType(Enum):
    SolidLine = 0
    SolidLineReverse = 1
    DashLine = 2
    DashLineReverse = 3

    def to_str(self):
        if self == ArrowType.SolidLine:
            return '->'
        elif self == ArrowType.DashLine:
            return '-->'
        elif self == ArrowType.SolidLineReverse:
            return '<-'
        elif self == ArrowType.DashLineReverse:
            return '<--'

    @staticmethod
    def from_str(s: str):
        if s == '->':
            return ArrowType.SolidLine
        elif s == '-->':
            return ArrowType.DashLine
        elif s == '<-':
            return ArrowType.SolidLineReverse
        elif s == '-->':
            return ArrowType.DashLineReverse


class WorkflowCmd:
    def __init__(self):
        pass

    @staticmethod
    def regex_pattern() -> str:
        pass

    @staticmethod
    def from_regex_match(s: str):
        pass


class CmdTarget:
    def __init__(self, name: str):
        self._name = name


class CmdSendMsg(WorkflowCmd):
    def __init__(self, sender: CmdTarget, receiver: CmdTarget, arrow: ArrowType, msg: str):
        WorkflowCmd.__init__(self)
        self._sender = sender
        self._receiver = receiver
        self._arrow_type = arrow
        self._msg = msg

    @staticmethod
    def regex_pattern():
        arrows = '|'.join(t.to_str() for t in ArrowType)
        return r'(.+?)\s*(%s)\s*(.+?)\s*:(.+)' % arrows

    @staticmethod
    def from_regex_match(s: str):
        match = re.search(CmdSendMsg.regex_pattern(), s)
        if match is None:
            return None
        sender = CmdTarget(match.group(1))
        arrow = ArrowType.from_str(match.group(2))
        receiver = CmdTarget(match.group(3))
        msg = match.group(4).strip()
        return CmdSendMsg(sender, receiver, arrow, msg)


class CmdAttribute(WorkflowCmd):
    def __init__(self):
        WorkflowCmd.__init__(self)
        pass


class CmdTitle(CmdAttribute):
    def __init__(self, title: str):
        CmdAttribute.__init__(self)
        self._title = title

    @staticmethod
    def regex_pattern():
        return r'title\b*:(.+)'

    @staticmethod
    def from_regex_match(s: str):
        match = re.search(CmdTitle.regex_pattern(), s)
        if match is None:
            return None
        return CmdTitle(match.group(1))


class CmdSpace(CmdAttribute):
    def __init__(self):
        CmdAttribute.__init__(self)
        pass

    @staticmethod
    def regex_pattern():
        return 'space'

    @staticmethod
    def from_regex_match(s: str):
        match = re.search(CmdSpace.regex_pattern(), s)
        if match is None:
            return None
        return CmdSpace()


class CmdActivate(CmdAttribute):
    def __init__(self, target: CmdTarget):
        CmdAttribute.__init__(self)
        self._target = target

    @staticmethod
    def regex_pattern():
        return r'activate\b+(\w+)'

    @staticmethod
    def from_regex_match(s: str):
        match = re.search(CmdActivate.regex_pattern(), s)
        if match is None:
            return None
        target = CmdTarget(match.group(1))
        return CmdActivate(target)


class CmdDeactivate(CmdAttribute):
    def __init__(self, target: CmdTarget):
        CmdAttribute.__init__(self)
        self._target = target

    @staticmethod
    def regex_pattern():
        return r'deactivate\b+(\w+)'

    @staticmethod
    def from_regex_match(s: str):
        match = re.search(CmdDeactivate.regex_pattern(), s)
        if match is None:
            return None
        target = CmdTarget(match.group(1))
        return CmdDeactivate(target)


class WorkflowBox(tk.Canvas):
    """
    Visualize a workflow (UML sequence diagram) on a canvas
    """
    _commands: List[WorkflowCmd]

    def __init__(self, master, *a, **kw):
        self._commands = []
        lines = kw.pop('content')
        lines = lines.split('\n')
        self.parse_cmd(lines)
        tk.Canvas.__init__(self, master, *a, **kw)

    def update_canvas(self):
        pass

    def parse_cmd(self, lines):
        for line in lines:
            for factory in cmd_factories:
                cmd = factory(line)
                if cmd is None:
                    continue
                self._commands.append(cmd)
                break

    def export_image(self):
        pass


def construct_regex_chain():
    return [CmdSendMsg.from_regex_match,
            CmdTitle.from_regex_match,
            CmdSpace.from_regex_match,
            CmdActivate.from_regex_match,
            CmdDeactivate.from_regex_match]


cmd_factories = []
if len(cmd_factories) == 0:
    cmd_factories = construct_regex_chain()


def unit_test_diagram():
    root = tk.Tk()
    workflow = WorkflowBox(root, content='Client 0 -> Server 1: AuthReq(clientId, UDID)')
    workflow.pack(fill=tk.BOTH, expand=tk.YES)
    root.mainloop()


if __name__ == "__main__":
    unit_test_diagram()
