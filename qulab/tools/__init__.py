class _Missing():

    def __repr__(self):
        return "Missing"


Missing = _Missing()


def connect_trace(*mappings):
    if not mappings:
        return {}
    result = {}
    first_mapping = mappings[0]
    for key in first_mapping:
        current_value = key
        trajectory = []
        for mapping in mappings:
            if current_value is Missing:
                trajectory.append(Missing)
                continue
            if current_value in mapping:
                next_value = mapping[current_value]
                trajectory.append(next_value)
                current_value = next_value
            else:
                trajectory.append(Missing)
                current_value = Missing
        result[key] = trajectory
    return result


def connect(*mappings):
    if not mappings:
        return {}
    return {
        k: v[-1]
        for k, v in connect_trace(*mappings).items() if v[-1] is not Missing
    }
