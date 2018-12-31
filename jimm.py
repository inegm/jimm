import sys
import time
import traceback

from PyQt5 import QtWidgets as QtW
from PyQt5 import QtCore as QtC
from PyQt5 import QtGui as QtG
import mido

from ui.jimmUI import Ui_MainWindow
from ji.mapper import MIDIMapper


class MainWindow(QtW.QMainWindow, Ui_MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Just Intonation MIDI Mapper')

        # For timestamps
        self.first_note = True
        self.start_time = None

        self.threadpool = QtC.QThreadPool()

        self.message_model = self.create_message_model(self.messages_tree)
        self.messages_tree.setModel(self.message_model)
        self.messages_tree.setFocus()

        self.bypass = False
        self.bypass_button.stateChanged.connect(self.toggle_bypass)

        self.voices_spin.valueChanged.connect(self.set_n_voices)

        self.midi_receive_name = self.get_midi_receive_name()
        self.midi_receive = mido.open_input(
            self.midi_receive_name,
            virtual=True
        )

        self.update_midi_inputs()
        self.refresh_midi_button.clicked.connect(self.update_midi_inputs)
        self.midi_input_combo.currentIndexChanged[str].connect(
            self.set_midi_input)

        self.midi_input_name = self.midi_input_combo.currentText()
        # self.in_port_label.setText(self.midi_input_name)
        self.midi_out_name = self.get_midi_out_name()
        # self.out_port_label.setText(self.midi_out_name)
        self.midi_output = mido.open_output(self.midi_out_name, virtual=True)

        self.mapper = MIDIMapper(self.midi_output)
        self.scale_combo.addItems(self.mapper.list_scales())
        self.scale_combo.currentIndexChanged[str].connect(
            self.set_mapper_scale)
        self.scale_root_combo.currentIndexChanged.connect(
            self.set_mapper_root)
        self.start_midi_listener()


    def create_message_model(self, parent):
        model = QtG.QStandardItemModel(0, 7, parent)
        model.setHeaderData(0, QtC.Qt.Horizontal, 'Timestamp')
        model.setHeaderData(1, QtC.Qt.Horizontal, 'Type')
        model.setHeaderData(2, QtC.Qt.Horizontal, 'Note in')
        model.setHeaderData(3, QtC.Qt.Horizontal, 'Note out')
        model.setHeaderData(4, QtC.Qt.Horizontal, 'Bend')
        model.setHeaderData(5, QtC.Qt.Horizontal, 'Velocity')
        model.setHeaderData(6, QtC.Qt.Horizontal, 'Channel')

        return model

    def add_message(self, message):
        self.message_model.insertRow(0)
        self.message_model.setData(
            self.message_model.index(0, 0), message.get('time'))
        self.message_model.setData(
            self.message_model.index(0, 1), message.get('type'))
        self.message_model.setData(
            self.message_model.index(0, 2), message.get('note_in'))
        self.message_model.setData(
            self.message_model.index(0, 3), message.get('note_out'))
        self.message_model.setData(
            self.message_model.index(0, 4), message.get('bend'))
        self.message_model.setData(
            self.message_model.index(0, 5), message.get('velocity'))
        self.message_model.setData(
            self.message_model.index(0, 6), message.get('channel') + 1)

    def set_mapper_scale(self, scale):
        self.mapper.scale = scale

    def set_mapper_root(self, root):
        self.mapper.root = root

    def set_n_voices(self, n_voices):
        self.mapper.max_concurrent_notes = n_voices

    def update_midi_inputs(self):
        self.midi_input_combo.clear()
        self.midi_input_combo.addItem(self.midi_receive_name)
        names = [
            name
            for name in mido.get_input_names()
            if 'JI Mapper' not in name
        ]
        self.midi_input_combo.addItems(names)

    def set_midi_input(self, input_name):
        self.midi_input_name = input_name
        # self.in_port_label.setText(self.midi_input_name)
        self.start_midi_listener()

    def get_midi_out_name(self):
        names = mido.get_input_names()
        count = 0
        for name in names:
            if 'JI Mapper ' in name:
                count +=1
        return f'JI Mapper {count} (from)'

    def get_midi_receive_name(self):
        names = mido.get_output_names()
        count = 0
        for name in names:
            if 'JI Mapper ' in name:
                count +=1
        return f'JI Mapper {count} (to)'

    def map_midi(self, msg):
        msg = self.mapper.map(msg, self.bypass)
        # Check for failed mapping (ex. dropped note)
        if msg is None:
            return
        if self.first_note:
            self.start_time = time.time()
            self.first_note = False
        delta_time = int(1000 * (time.time() - self.start_time))
        if delta_time > 10000:
            self.start_time = time.time()
            delta_time = 0
            # FIXME :
            # self.message_model.reset()
        msg.update({'time': delta_time})
        self.add_message(msg)
        self.midi_output.send(mido.Message(
            type=msg.get('type'),
            note=msg.get('note_out'),
            velocity=msg.get('velocity'),
            channel=msg.get('channel')
        ))
        self.midi_output.send(mido.Message(
            'pitchwheel',
            pitch=msg.get('bend'),
            channel=msg.get('channel')
        ))

    def get_midi_input(self, port):
        if port == self.midi_receive_name:
            with self.midi_receive as in_port:
                for msg in in_port:
                    if msg.type not in ['note_on', 'note_off']:
                        continue
                    self.map_midi(msg)
        else:
            with mido.open_input(port) as in_port:
                for msg in in_port:
                    if msg.type not in ['note_on', 'note_off']:
                        continue
                    self.map_midi(msg)

    def start_midi_listener(self):
        self.midi_input = Worker(
            self.get_midi_input,
            port=self.midi_input_name
        )
        self.threadpool.start(self.midi_input)

    def toggle_bypass(self, state):
        self.bypass = state == QtC.Qt.Checked

    def closeEvent(self, event):
        self.midi_output.close()
        self.midi_receive.close()


class WorkerSignals(QtC.QObject):
    finished = QtC.pyqtSignal()
    error = QtC.pyqtSignal(tuple)
    result = QtC.pyqtSignal(object)


class Worker(QtC.QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @QtC.pyqtSlot()
    def run(self):
        try:
            result = self.fn(
                *self.args,
                **self.kwargs,
                # status=self.signals.status,
                # progress=self.signals.progress
            )
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


if __name__ == '__main__':
    app = QtW.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()
