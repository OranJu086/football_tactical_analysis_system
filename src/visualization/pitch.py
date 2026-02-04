from mplsoccer import Pitch


def create_pitch():
    pitch = Pitch(
        pitch_type='statsbomb',
        pitch_color='white',
        line_color='black'
    )
    fig, ax = pitch.draw(figsize=(10, 7))
    return pitch, fig, ax