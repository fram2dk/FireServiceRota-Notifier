
def merge_with_mask(target, source, mask):
    for key, mask_val in mask.items():
        if mask_val is True:
            # Kopier hele værdien fra source hvis den findes
            if key in source:
                target[key] = source[key]
        elif isinstance(mask_val, dict):
            # Sørg for at mål har en dict at skrive i
            target.setdefault(key, {})
            src_sub = source.get(key, {})
            tgt_sub = target[key]
            # Hvis source ikke er dict, overskriv kun hvis mask siger True
            if not isinstance(src_sub, dict):
                # Hvis mask er dict men source ikke er dict, spring over eller sæt direkte
                continue
            merge_with_mask(tgt_sub, src_sub, mask_val)
        # andre mask-typer ignoreres
    return target

