import rextio


@rextio.native
def count_primes(limit: int) -> int:
    count = 0
    for candidate in range(2, limit):
        prime = True
        divisor = 2
        while divisor * divisor <= candidate:
            if candidate % divisor == 0:
                prime = False
                break
            divisor += 1
        if prime:
            count += 1
    return count


@rextio.native
def main(argv: list[str]) -> int:
    limit = 30000 * len(argv)
    print(count_primes(limit))
    return 0
