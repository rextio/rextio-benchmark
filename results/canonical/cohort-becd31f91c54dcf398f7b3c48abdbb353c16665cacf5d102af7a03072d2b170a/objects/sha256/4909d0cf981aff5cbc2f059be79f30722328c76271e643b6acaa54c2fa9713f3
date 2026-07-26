from rextio_pandas.types import SeriesBool, SeriesF64


def scale(value: float) -> float:
    return value * 1.75


def shift(value: float) -> float:
    return value + 0.25


def predicate(value: float) -> bool:
    return (value > 0.0 and value != 7.0) or False


def map_pipeline(series: SeriesF64) -> SeriesBool:
    scaled = series.map(scale)
    shifted = scaled.map(shift)
    return shifted.map(predicate)

