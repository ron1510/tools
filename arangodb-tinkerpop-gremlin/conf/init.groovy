def addItUp(x, y) { x + y }

def globals = [:]
globals << ["${GREMLIN_TRAVERSAL_SOURCE}": traversal().withEmbedded(graph)]
