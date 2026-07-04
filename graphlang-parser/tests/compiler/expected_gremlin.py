OUT_VERTEX_STEP = (
    ".flatMap{def s=it.get().toString(); "
    "def target=s.substring(s.indexOf('->')+2, s.length()-1); "
    "g.V(target)}"
)

IN_VERTEX_STEP = (
    ".flatMap{def s=it.get().toString(); "
    "def body=s.substring(s.lastIndexOf('[')+1, s.length()-1); "
    "def arrow=body.indexOf('->'); def label=it.get().label(); "
    "def sourcePart=body.substring(0, arrow); "
    "def source=sourcePart.substring(0, sourcePart.length()-label.length()-1); "
    "g.V(source)}"
)

ANY_VERTEX_STEP = (
    ".flatMap{def current=it.path().get('opium_current_vertex').id(); "
    "def s=it.get().toString(); "
    "def body=s.substring(s.lastIndexOf('[')+1, s.length()-1); "
    "def arrow=body.indexOf('->'); def label=it.get().label(); "
    "def sourcePart=body.substring(0, arrow); "
    "def source=sourcePart.substring(0, sourcePart.length()-label.length()-1); "
    "def target=body.substring(arrow+2); "
    "def other=current == source ? target : source; g.V(other)}"
)

SOURCE_ID_STEP = (
    ".map{def s=it.get().toString(); "
    "def body=s.substring(s.lastIndexOf('[')+1, s.length()-1); "
    "def arrow=body.indexOf('->'); def label=it.get().label(); "
    "def sourcePart=body.substring(0, arrow); "
    "sourcePart.substring(0, sourcePart.length()-label.length()-1)}"
)

TARGET_ID_STEP = (
    ".map{def s=it.get().toString(); "
    "s.substring(s.indexOf('->')+2, s.length()-1)}"
)

LOGICAL_ID_MAP = (
    ".map{def id=it.get(); def slash=id.indexOf('/'); "
    "slash < 0 ? id.replace('___', '.') : "
    "id.substring(0, slash).replace('___', '.') + id.substring(slash)}"
)
