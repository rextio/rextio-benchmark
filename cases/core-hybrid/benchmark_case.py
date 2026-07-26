def make_arguments(_benchmark_id: str) -> tuple[object, ...]:
    values = [((index * 37) % 1009) - 504 for index in range(4096)]
    return values, 48, 17


def normalize(_benchmark_id: str, value: object) -> object:
    return value

