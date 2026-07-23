import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from ui import Ui_MainWindow


class MyWidget(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.run)

    def run(self):
        if self.radioButton.isChecked():
            self.graphicsView.clear()
            self.graphicsView.plot([i for i in range(10)], [i for i in range(10)], pen='r')
        elif self.radioButton_2.isChecked():
            self.graphicsView.clear()
            self.graphicsView.plot([i for i in range(10)], [i ** 2 for i in range(10)], pen='g')
        elif self.radioButton_3.isChecked():
            self.graphicsView.clear()
            self.graphicsView.plot([i for i in range(10)], [i ** 3 for i in range(10)], pen='b')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyWidget()
    ex.show()
    sys.exit(app.exec())