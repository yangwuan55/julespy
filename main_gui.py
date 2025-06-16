import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTabWidget, QLabel, QMenuBar, QMessageBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt # Import Qt for AlignCenter etc.

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("简易量化分析助手 (Simple Quant Analysis Assistant)")
        self.setGeometry(100, 100, 1200, 800)  # x, y, width, height

        # Central Widget and Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create Tab Widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Import and add Strategy Configuration Tab
        from gui_strategy_config_tab import StrategyConfigTab # Assuming it's in the same directory or sys.path is set
        strategy_config_tab = StrategyConfigTab()
        self.tab_widget.addTab(strategy_config_tab, "策略配置 (Strategy Config)")

        # Import and add Data Management Tab
        from gui_data_management_tab import DataManagementTab
        data_management_tab = DataManagementTab()
        self.tab_widget.addTab(data_management_tab, "数据管理 (Data Management)")

        # Import and add Backtesting Tab
        from gui_backtesting_tab import BacktestingTab
        backtesting_tab = BacktestingTab()
        self.tab_widget.addTab(backtesting_tab, "回测分析 (Backtesting)")

        # Import and add Simulation Tab
        from gui_simulation_tab import SimulationTab
        simulation_tab = SimulationTab()
        self.tab_widget.addTab(simulation_tab, "模拟交易 (Simulated Trading)")

        # Import and add Report Viewer Tab
        from gui_report_viewer_tab import ReportViewerTab
        report_viewer_tab = ReportViewerTab()
        self.tab_widget.addTab(report_viewer_tab, "报告查看 (Report Viewer)")

        # Create Menu Bar
        self._create_menu_bar()

    def add_placeholder_tab(self, title):
        """Helper function to add a placeholder tab."""
        placeholder_widget = QWidget()
        layout = QVBoxLayout(placeholder_widget)
        label = QLabel(f"Content for {title}")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.tab_widget.addTab(placeholder_widget, title)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("文件 (&File)")

        import_strategy_action = QAction("导入策略 (Import Strategy)", self)
        # import_strategy_action.triggered.connect(self.import_strategy) # Placeholder
        file_menu.addAction(import_strategy_action)

        export_strategy_action = QAction("导出策略 (Export Strategy)", self)
        # export_strategy_action.triggered.connect(self.export_strategy) # Placeholder
        file_menu.addAction(export_strategy_action)

        file_menu.addSeparator()

        exit_action = QAction("退出 (Exit)", self)
        exit_action.triggered.connect(self.close) # Connect to QMainWindow.close
        file_menu.addAction(exit_action)

        # Help Menu
        help_menu = menu_bar.addMenu("帮助 (&Help)")

        about_action = QAction("关于 (About)", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "关于 (About)",
            "简易量化分析助手 v0.1\nSimple Quant Analysis Assistant"
        )

    # Placeholder methods for menu actions (to be implemented later)
    # def import_strategy(self):
    #     print("Placeholder: Import Strategy triggered")

    # def export_strategy(self):
    #     print("Placeholder: Export Strategy triggered")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
