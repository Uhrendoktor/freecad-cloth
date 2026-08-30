"""One-step Pattern workbench command for native Sketcher authoring."""

def create_native_pattern_piece(name="PatternPiece", width=100.0, height=60.0, allowance=0.0, grainline=0.0):
    import FreeCADGui as Gui
    from PatternCommands import create_pattern_piece_from_parameters, create_pattern_sketch
    piece = create_pattern_piece_from_parameters(name, width, height, allowance, grainline)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    sketch = create_pattern_sketch()
    piece.GeometryMode = "Sketch"
    piece.GeometryAuthority = "Sketcher"
    sketch.GeometryAuthority = "Sketcher"
    return piece, sketch

def _active_document():
    try:
        import FreeCAD as App
        return App.ActiveDocument is not None
    except ImportError:
        return False

class _NativePatternCommand:
    def Activated(self): return create_native_pattern_piece()
    def IsActive(self): return _active_document()
    def GetResources(self): return {"MenuText": "New Native Pattern Piece", "ToolTip": "Create a PatternPiece and immediately make its native Sketcher geometry authoritative"}

COMMANDS=["ClothPattern_CreateNativePiece"]
try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothPattern_CreateNativePiece", _NativePatternCommand())
except (ImportError,AttributeError): pass
