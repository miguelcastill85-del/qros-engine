"""Classify native startup evidence without hiding a QROS ANR."""


def startup_state(root, package):
    nodes = list(root.iter('node'))
    labels = [n.get('text', '') or n.get('content-desc', '') for n in nodes]
    anrs = [s for s in labels if "isn't responding" in s]
    if anrs:
        if (anrs == ["Pixel Launcher isn't responding"]
                and any(n.get('package') == 'android'
                        and n.get('class') == 'android.widget.Button'
                        and n.get('text') == 'Close app' for n in nodes)):
            return 'launcher_anr'
        raise RuntimeError('unexpected application ANR; startup denied')
    app_labels = [n.get('text', '') or n.get('content-desc', '')
                  for n in nodes if n.get('package') == package]
    if (any('QROS' in s for s in app_labels)
            and any('Más módulos y seguridad' in s for s in app_labels)):
        return 'home'
    return 'waiting'
