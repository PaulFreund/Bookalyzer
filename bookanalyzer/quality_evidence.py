"""Complete location index, bounded excerpts, and reversible review decisions."""
from collections import Counter, defaultdict


def decision_key(profile, evidence, chapter_index=None):
    return f"{profile['textSha256']}:{chapter_index}:{evidence['metric']}:{evidence['start']}:{evidence['end']}"


def excerpt_at(text, metric, start, end, label):
    return dict(metric=metric, start=start, end=end, label=label,
                before=text[max(0, start - 90):start], text=text[start:min(end, start + 220)],
                after=text[end:end + 90], truncated=end - start > 220)


def indexed(profile):
    for metric, locations in profile["evidenceIndex"].items():
        for start, end, label in locations:
            yield dict(metric=metric, start=start, end=end, label=label)


def reviewed(profile, decisions, chapter_index=None):
    ignored = set(decisions)
    for evidence in indexed(profile):
        key = decision_key(profile, evidence, chapter_index)
        yield {**evidence, "key": key, "intentional": key in ignored}


def review_overview(profile, text, decisions, chapter_index=None):
    """Keep six OPEN examples per rule; counts cover every indexed location."""
    intentional, selected = Counter(), defaultdict(list)
    for evidence in reviewed(profile, decisions, chapter_index):
        metric = evidence["metric"]
        if evidence["intentional"]:
            intentional[metric] += 1
        elif len(selected[metric]) < 6:
            selected[metric].append({**excerpt_at(text, metric, evidence["start"], evidence["end"], evidence["label"]),
                                     "key": evidence["key"], "intentional": False})
    profile["evidence"] = [e for examples in selected.values() for e in examples]
    profile["intentionalCounts"] = dict(intentional)


def findings_page(profile, text, decisions, chapter_index, metric, status, offset, limit):
    rows = [e for e in reviewed(profile, decisions, chapter_index)
            if (metric is None or e["metric"] == metric)
            and (status == "all" or e["intentional"] == (status == "intentional"))]
    rows.sort(key=lambda e: (e["start"], e["end"], e["metric"]))
    # Removing the last open finding on a page returns the preceding page.
    offset = min(offset, max(0, (len(rows) - 1) // limit * limit))
    return dict(total=len(rows), offset=offset, limit=limit, textSha256=profile["textSha256"],
                items=[{**excerpt_at(text, e["metric"], e["start"], e["end"], e["label"]),
                        "key": e["key"], "intentional": e["intentional"]}
                       for e in rows[offset:offset + limit]])
