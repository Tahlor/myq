from tools.historical_mcu_protocol import crc8, extract_frames, parse_frame, summarize


PUBLIC_OPEN = "P80111021110020501020100247259FA41000000000D74"
PUBLIC_CLOSE = "P60111021110020501020100247259FA41000000000E53"
PUBLIC_OPENING = "P2011102110F008601B31FA00000000000810460428B"
PUBLIC_OPENED = "P3011102110F008601B31FA000000000008101604202"
PUBLIC_CLOSING = "P7011102110F008601B31FA000000000008105604204"
PUBLIC_CLOSED = "P0011102110F008601B31FA00000000000810260428E"
PUBLIC_IDLE_CLOSED = "P1011102110F008601B31FA0000000000081026040B4"


def test_public_checksum_parameters_fit_known_samples():
    for raw in (
        PUBLIC_OPEN,
        PUBLIC_CLOSE,
        PUBLIC_OPENING,
        PUBLIC_OPENED,
        PUBLIC_CLOSING,
        PUBLIC_CLOSED,
        PUBLIC_IDLE_CLOSED,
        "P00111021110021A0100000010000000000000000000B6",
        "P5010102010101DB",
        "P6010102010203013E",
    ):
        frame = parse_frame(raw)
        assert frame.checksum_valid
        assert crc8(frame.payload) == frame.checksum


def test_rotating_p_prefix_is_not_covered_by_checksum():
    # The public capture repeats identical status payloads under different P<n>
    # prefixes with the same checksum, proving that nibble is transport/log
    # sequencing rather than CRC input.
    a = parse_frame(PUBLIC_IDLE_CLOSED)
    b = parse_frame("P2011102110F008601B31FA0000000000081026040B4")
    assert a.payload == b.payload
    assert a.checksum == b.checksum
    assert a.sequence != b.sequence


def test_labelled_historical_action_hypothesis():
    assert parse_frame(PUBLIC_OPEN).historical_action == "open"
    assert parse_frame(PUBLIC_CLOSE).historical_action == "close"


def test_labelled_historical_state_hypothesis():
    assert parse_frame(PUBLIC_OPENING).historical_state == "opening"
    assert parse_frame(PUBLIC_OPENED).historical_state == "open"
    assert parse_frame(PUBLIC_CLOSING).historical_state == "closing"
    assert parse_frame(PUBLIC_CLOSED).historical_state == "closed"
    assert parse_frame(PUBLIC_IDLE_CLOSED).historical_state == "closed"


def test_invalid_checksum_does_not_receive_semantics():
    broken = parse_frame(PUBLIC_OPEN[:-2] + "00")
    assert not broken.checksum_valid
    assert broken.historical_kind is None
    assert broken.historical_action is None


def test_extract_and_summarize_public_excerpt():
    text = f"""
; command open from wall button
<{PUBLIC_OPEN}>
<{PUBLIC_OPENING}>
; finished opening
<{PUBLIC_OPENED}>
; command close
<{PUBLIC_CLOSE}>
<{PUBLIC_CLOSING}>
; finished closing
<{PUBLIC_CLOSED}>
"""
    frames = extract_frames(text)
    report = summarize(frames)
    assert report["frames"] == 6
    assert report["checksum_invalid"] == 0
    assert report["historical_actions"] == {"open": 1, "close": 1}
    assert report["historical_states"] == {
        "opening": 1,
        "open": 1,
        "closing": 1,
        "closed": 1,
    }
