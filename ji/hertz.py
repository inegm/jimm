from math import log2, floor


def hertz_to_midi(hertz, a4_hertz=440.0):
    """Frequency to MIDI note number conversion.

    :param hertz: Frequency in Hertz
    :type hertz: float
    :param a4_hertz: A4 reference frequency
    :type a4_hertz: float

    :returns: MIDI note number and pitch bend value (in range 0, 8192)
    :rtype: tuple (int, int)

    **Examples**

    >>> hertz_to_midi(440)
    (69, 0)

    >>> hertz_to_midi(450)
    (69, 1594)
    """
    if hertz <= 0:
        raise TypeError('hertz must be > 0')
    if a4_hertz <= 0:
        raise TypeError('a4_hertz must be > 0')
    oct_div = 12  # Equal temperament
    a4_midi = 69
    midi = oct_div * log2(hertz / a4_hertz) + a4_midi
    bend = cents_to_midi_bend(100 * divmod(midi, int(midi))[1])

    return floor(midi), bend


def cents_to_midi_bend(cents):
    """Cents to MIDI pitch bend value.

    :param cents: Cents
    :type cents: float

    :rtype: int

    **Reference**
    http://www.elvenminstrel.com/music/tuning/reference/pitchbends.shtml

    **Eamples**

    >>> cents_to_midi_bend(1.96)
    80

    >>> cents_to_midi_bend(47.41)
    1942

    >>> cents_to_midi_bend(-15.64)
    -641

    >>> cents_to_midi_bend(100)
    4096
    """
    return round(cents * (8192 / 200))


def midi_to_hertz(midi, a4_hertz=440.0):
    """MIDI note number to to frequency conversion.

    :param midi: MIDI note number
    :type midi: int
    :param a4_hertz: A4 reference frequency
    :type a4_hertz: float

    :returns: Frequency in Hertz
    :rtype: float

    **Examples**

    >>> midi_to_hertz(69)
    440.0

    >>> midi_to_hertz(0)
    8.175798915643707
    """
    if (not isinstance(midi, int)) or (midi not in range(0, 128)):
        raise TypeError('midi must be int and 128 > midi >= 0')
    if a4_hertz <= 0:
        raise TypeError('a4_hertz must be > 0')
    oct_div = 12  # Equal temperament
    a4_midi = 69
    return 2**((midi - a4_midi) / oct_div) * a4_hertz


def hertz_cents(fhz, ghz):
    """Cents distance between two frequencies.

    :param fhz: First frequency in Hertz
    :type fhz: float
    :param ghz: Second frequency in Hertz
    :type ghz: float

    :returns: Distance between two frequencies in cents
    :rtype: float

    **Examples**

    >>> round(hertz_cents(440, 660), 3)
    701.955

    >>> hertz_cents(440, 880)
    1200.0
    """
    if not (isinstance(fhz, int) and isinstance(ghz, int)):
        raise TypeError('invalid frequency values')
    if not ((fhz > 0) and (ghz > 0)):
        raise TypeError('invalid frequency values')
    return 1200 * log2(ghz / fhz)
