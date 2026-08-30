"""Headless validation and inspection helpers for the Sewing workbench."""
def _pattern_pieces(doc): return [o for o in getattr(doc,"Objects",()) if getattr(o,"PatternType","")=="PatternPiece"]
def _seams(doc): return [o for o in getattr(doc,"Objects",()) if getattr(o,"SeamId","")]
def _networks(doc): return [o for o in getattr(doc,"Objects",()) if getattr(o,"SewingType","")=="SewingNetwork"]
def seam_diagnostic(seam,piece_map=None):
    status=str(getattr(seam,"Status","Valid")) or "Valid"; seam_id=str(getattr(seam,"SeamId","")) or getattr(seam,"Name","<unnamed>")
    result={"id":seam_id,"status":status,"reversed":bool(getattr(seam,"ReversedB",False)),"piece_a":str(getattr(seam,"PieceA","")),"piece_b":str(getattr(seam,"PieceB","")),"edge_a":str(getattr(seam,"EdgeAId",getattr(seam,"EdgeA",""))),"edge_b":str(getattr(seam,"EdgeBId",getattr(seam,"EdgeB",""))),"length_a":float(getattr(seam,"LengthA",0.0) or 0.0),"length_b":float(getattr(seam,"LengthB",0.0) or 0.0),"difference":float(getattr(seam,"LengthDifference",0.0) or 0.0),"message":status}
    if piece_map:
        try:
            from SewingObjects import _seam_length
            result["length_a"]=_seam_length(piece_map[result["piece_a"]],seam,"A"); result["length_b"]=_seam_length(piece_map[result["piece_b"]],seam,"B"); result["difference"]=abs(result["length_a"]-result["length_b"])
        except (KeyError,TypeError,ValueError,RuntimeError,AttributeError) as exc:
            if status!="Valid" and (result["length_a"]<=0.0 or result["length_b"]<=0.0): result["status"]="Invalid"; result["message"]="Unable to resolve seam geometry: %s"%exc; return result
    if status=="Valid": result["message"]="valid%s"%( "; B direction reversed" if result["reversed"] else "")
    elif status=="Changed reference": result["message"]="edge geometry changed; repair or recreate this seam"
    elif status=="Missing reference": result["message"]="referenced edge is missing; repair or recreate this seam"
    elif status=="Length mismatch": result["message"]="seam lengths differ by %.3f mm"%result["difference"]
    return result
def validate_sewing_graph(doc,tolerance=0.5):
    pieces=_pattern_pieces(doc); piece_map={str(getattr(p,"PieceId","")):p for p in pieces}; seams=_seams(doc); networks=_networks(doc); diagnostics=[seam_diagnostic(s,piece_map) for s in seams]; invalid=[]; connected=set()
    for item in diagnostics:
        if item["piece_a"] in piece_map and item["piece_b"] in piece_map and item["status"]=="Valid": connected.update((item["piece_a"],item["piece_b"]))
        if item["status"]!="Valid": invalid.append(item)
    network_diagnostics=[]
    for network in networks:
        status=str(getattr(network,"Status","Incomplete")); members=tuple(getattr(network,"Seams",()) or ()); item={"id":str(getattr(network,"RelationshipId","")) or getattr(network,"Name","<unnamed>"),"status":status,"segments":len(members),"difference":float(getattr(network,"LengthDifference",0.0))}; network_diagnostics.append(item)
        for member in members:
            a=str(getattr(member,"PieceA","")); b=str(getattr(member,"PieceB",""))
            if a in piece_map and b in piece_map and str(getattr(member,"Status","Valid"))=="Valid": connected.update((a,b))
        if status!="Valid": invalid.append({"id":item["id"],"status":status,"message":str(getattr(network,"InvalidReason",""))})
    isolated=sorted(pid for pid in piece_map if pid not in connected); mismatch=[item for item in diagnostics if item["status"]=="Length mismatch"]
    if invalid: status="Invalid"; message="Invalid sewing graph: "+"; ".join("%s (%s)"%(x["id"],x["status"]) for x in invalid)
    elif mismatch: status="Length mismatch"; message="Length mismatch in: "+", ".join(x["id"] for x in mismatch)
    elif isolated: status="Incomplete"; message="Unsewn pattern pieces: "+", ".join(isolated)
    elif not pieces: status="Incomplete"; message="No pattern pieces in the document"
    else: status="Valid"; message="Complete sewing graph"
    return {"status":status,"message":message,"piece_count":len(pieces),"seam_count":len(seams),"network_count":len(networks),"isolated":tuple(isolated),"seams":tuple(diagnostics),"networks":tuple(network_diagnostics),"tolerance":float(tolerance)}
