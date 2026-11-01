"""Pre-optimization traversal from 684f295; differential test reference only."""
import os
from pathlib import Path
import stat
from storymotion.local_state import _unsafe, _root, _check, guard_control


def old_guard_project_scope(project):
    try:
        if Path(project).is_symlink():_unsafe()
        root = _root(project, True)
        for name in ('node_modules', 'work', '.runtime'):guard_control(root, name, 'dir')
        guard_control(root, 'optional/remotion/node_modules', 'dir')
        for name in ('.runtime/chrome', '.runtime/npm-cache', '.runtime/setup-state'):guard_control(root, name, 'dir')
        pending = [root / 'work', root / '.runtime']
        while pending:
            folder = pending.pop()
            if _check(folder, 'dir') is None:continue
            if folder in {root / '.runtime/chrome', root / '.runtime/probe/stages'}:continue
            with os.scandir(folder) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        guard_control(root, path.relative_to(root), 'dir');pending.append(path)
                    else:guard_control(root, path.relative_to(root), 'file')
        return root
    except (OSError, ValueError, TypeError):_unsafe()
