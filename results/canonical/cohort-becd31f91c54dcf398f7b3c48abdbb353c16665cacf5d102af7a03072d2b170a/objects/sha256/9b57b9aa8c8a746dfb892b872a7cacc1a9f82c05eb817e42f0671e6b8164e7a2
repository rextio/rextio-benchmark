import rextio


@rextio.native
def score(values: list[int], rounds: int, bias: int) -> int:
    total = 0
    for round_index in range(rounds):
        for value in values:
            mixed = value + bias + round_index
            if mixed % 2 == 0:
                total += mixed * mixed
            else:
                total += mixed + 3
    return total
