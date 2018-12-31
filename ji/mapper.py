import mido

from jintonic.intervals import JustInterval
from jintonic.scales import JustScale
from .hertz import midi_to_hertz, hertz_to_midi, cents_to_midi_bend


class MIDIMapper():
    def __init__(self, midi_output, verbose=False):
        self._scale = None
        self._root = 0
        self._max_concurrent_notes = 16
        self.scale_name = None
        self.scales = self.load_scales()
        self.verbose = verbose
        self.midi_output = midi_output
        self.active_notes = []  # FIFO Queue of (note, chan) tuples
        self.dropped_notes = []  # Note numbers of dropped notes to be ignored
        self.scale = "Harmonic Duodene of C (12 tone)"

    @property
    def max_concurrent_notes(self):
        return self._max_concurrent_notes

    @max_concurrent_notes.setter
    def max_concurrent_notes(self, max_n):
        self.clear_active_notes()
        if max_n > 16:
            max_n = 16
        elif max_n < 1:
            max_n = 1
        self._max_concurrent_notes = max_n

    @property
    def root(self):
        return self._root

    @root.setter
    def root(self, root):
        self.clear_active_notes()
        if root not in range(12):
            raise ValueError(f'invalid root: "{root}". (0 <= root < 12)')
        self._root = root

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, scale):
        self.clear_active_notes()
        self._scale = JustScale(
            [JustInterval(n, d) for n, d in self.scales[scale]]
        )
        self.scale_name = scale

    def clear_active_notes(self):
        for note, channel in self.active_notes:
            mido.send(mido.Message(
                'note_off',
                note=note,
                channel=channel
            ))
        self.active_notes = []

    def load_scales(self):
        return {
            "Harmonic Duodene of C (12 tone)": [
                (1, 1), (16, 15), (9, 8), (6, 5), (5, 4), (4, 3), (45, 32),
                (3, 2), (8, 5), (5, 3), (9, 5), (15, 8), (2, 1)
            ],
            "Young's Well-tuned piano (12 tone)": [
                (1, 1), (567, 512), (9, 8), (147, 128), (21, 16), (1323, 1024),
                (189, 128), (3, 2), (49, 32), (7, 4), (441, 256), (63, 32),
                (2, 1)
            ],
            "Archytas' Enharmonic (7 tone)": [
                (1, 1), (1, 1), (28, 27), (28, 27), (16, 15), (4, 3), (4, 3),
                (3, 2), (3, 2), (14, 9), (14, 9), (8, 5), (2, 1)
            ],
        }

    def list_scales(self):
        scales = self.load_scales()
        return scales.keys()

    def map(self, msg, bypass=False):
        if self.verbose:
            print(f'\nMapping {msg}')
            print(f'active: {self.active_notes}')
            print(f'dropped: {self.dropped_notes}')
        if not bypass:
            note_out, bend_out = self.map_note(msg.note)
        else:
            note_out = msg.note
            bend_out = 0
        channel = self.assign_channel(msg)
        if self.verbose:
            print(f'Assigning')
            print(f'active: {self.active_notes}')
            print(f'dropped: {self.dropped_notes}\n')

        if channel is None:
            return None
        msg = {
            'time': msg.time,
            'type': msg.type,
            'note_in': msg.note,
            'note_out': note_out,
            'bend': bend_out,
            'velocity': msg.velocity,
            'channel': channel
        }
        return msg

    def map_note(self, note):
        octave_divisions = 12
        octave, pclass = divmod(note - self.root, octave_divisions)
        fundamental = midi_to_hertz(octave * 12 + self.root)
        midi_note, bend = hertz_to_midi(fundamental * self.scale.tones[pclass])
        if self.scale_name == "Young's Well-tuned piano (12 tone)":
            # Major hack but *shrug*
            bend -= cents_to_midi_bend(74.7)
        return (midi_note, bend)

    def assign_channel(self, msg):
        # Some keyboards use velocity 0 to set note off.
        if (msg.type == 'note_on') and (msg.velocity > 0):
            if self.verbose:
                print('Got note ON')
            # Get first available channel
            active_chs = set([c for _, c in self.active_notes])
            available_chs = set(range(self.max_concurrent_notes)) - active_chs

            if available_chs == set():
                # If there are no available channels, rotate out (FIFO) and
                # steal a channel.
                dropped_note = self.active_notes[0][0]
                stolen_ch = self.active_notes[0][1]
                self.midi_output.send(mido.Message(
                    'note_off',
                    note=dropped_note,
                    channel=stolen_ch
                ))
                self.dropped_notes.append(dropped_note)
                self.active_notes = self.active_notes[1:]
                channel = stolen_ch
            else:
                # Get the first available channel
                channel = sorted(available_chs)[0]
            self.active_notes.append((msg.note, channel))

        elif (msg.type == 'note_off') or (msg.velocity == 0):
            if self.verbose:
                print('Got note OFF')
            if msg.note in self.dropped_notes:
                # Remove from the dropped list and ignore msg
                self.dropped_notes.remove(msg.note)
                channel = None
            else:
                # Remove the note from the active notes FIFO queue
                for i, t in enumerate(self.active_notes):
                    note, channel = t
                    if msg.note == note:
                        self.active_notes = (
                            self.active_notes[:i] +
                            self.active_notes[i+1: ]
                        )
                        break

        else:
            raise VelueError('invalid message type.')

        return channel
