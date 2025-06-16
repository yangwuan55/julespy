import sys
import os
import json # For strategy_config if needed, though load_strategy_config handles it
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QTextEdit, QLineEdit, QMessageBox, QScrollArea
)
from PySide6.QtGui import QPixmap, QDoubleValidator
from PySide6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import data_manager
import strategy_configurator
import backtesting_engine # For run_backtest
import reporting # For calculate_trade_statistics, generate_text_report

STRATEGIES_DIR_GUI = strategy_configurator.STRATEGIES_DIR # "strategies"
DATA_DIR_GUI = "data" # data_manager.py uses "data/" implicitly.
REPORTS_DIR_GUI = reporting.REPORTS_DIR # "reports"


class BacktestingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Configuration Section ---
        config_group = QGroupBox("回测配置 (Backtest Configuration)")
        config_layout = QFormLayout()

        self.strategy_file_combo = QComboBox()
        config_layout.addRow(QLabel("策略配置文件 (Strategy Config File):"), self.strategy_file_combo)

        self.data_file_combo = QComboBox()
        config_layout.addRow(QLabel("数据文件 (Data File):"), self.data_file_combo)

        self.initial_cash_edit = QLineEdit("100000.0")
        self.initial_cash_edit.setValidator(QDoubleValidator(0.0, 1.0e9, 2)) # Min, Max, Decimals
        config_layout.addRow(QLabel("初始资金 (Initial Cash):"), self.initial_cash_edit)

        button_layout = QHBoxLayout()
        self.refresh_files_button = QPushButton("刷新文件列表 (Refresh File Lists)")
        self.refresh_files_button.clicked.connect(self.populate_file_combos)
        button_layout.addWidget(self.refresh_files_button)

        self.run_backtest_button = QPushButton("开始回测 (Start Backtest)")
        self.run_backtest_button.clicked.connect(self.execute_backtest)
        button_layout.addWidget(self.run_backtest_button)
        config_layout.addRow(button_layout)

        config_group.setLayout(config_layout)
        self.main_layout.addWidget(config_group)

        # --- Results Display Section ---
        self.results_group = QGroupBox("回测结果 (Backtest Results)")
        results_main_layout = QVBoxLayout() # Main layout for results group

        # Use QHBoxLayout to place stats text and equity curve side-by-side or scrollable area
        results_content_layout = QHBoxLayout()

        self.stats_text_edit = QTextEdit()
        self.stats_text_edit.setReadOnly(True)
        results_content_layout.addWidget(self.stats_text_edit, 1) # Stretch factor 1

        # Scroll area for the equity curve image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.equity_curve_label = QLabel("回测完成后将在此显示图表 (Equity curve will be displayed here after backtest.)")
        self.equity_curve_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equity_curve_label.setMinimumSize(400,300) # Give it a minimum size
        self.scroll_area.setWidget(self.equity_curve_label)
        results_content_layout.addWidget(self.scroll_area, 1) # Stretch factor 1

        results_main_layout.addLayout(results_content_layout)
        self.results_group.setLayout(results_main_layout)
        self.main_layout.addWidget(self.results_group)

        self.populate_file_combos()

    def _populate_combo_box(self, combo_box, directory, extension_filters):
        combo_box.clear()
        if not os.path.exists(directory):
            # QMessageBox.warning(self, "目录错误", f"目录 '{directory}' 不存在.")
            print(f"Warning: Directory '{directory}' not found for combo box.")
            combo_box.addItem(f"目录 '{directory}' 未找到 (Directory not found)")
            combo_box.setEnabled(False)
            return

        combo_box.setEnabled(True)
        files = [f for f in os.listdir(directory) if any(f.endswith(ext) for ext in extension_filters)]
        if not files:
            combo_box.addItem("无可用文件 (No files available)")
        else:
            combo_box.addItems(files)

    def populate_file_combos(self):
        self._populate_combo_box(self.strategy_file_combo, STRATEGIES_DIR_GUI, [".json"])
        self._populate_combo_box(self.data_file_combo, DATA_DIR_GUI, [".csv", ".xlsx"])
        self.stats_text_edit.clear()
        self.equity_curve_label.setText("请运行回测以查看图表 (Run backtest to view chart).")
        self.equity_curve_label.setPixmap(QPixmap()) # Clear image


    def execute_backtest(self):
        self.stats_text_edit.clear()
        self.equity_curve_label.setText("回测运行中... (Backtest running...)")
        self.equity_curve_label.setPixmap(QPixmap()) # Clear previous image
        QApplication.processEvents() # Update UI

        strategy_filename = self.strategy_file_combo.currentText()
        data_filename = self.data_file_combo.currentText()

        if not strategy_filename or "无可用文件" in strategy_filename or "目录" in strategy_filename :
            QMessageBox.warning(self, "配置错误", "请选择一个有效的策略配置文件.")
            self.equity_curve_label.setText("回测配置错误 (Backtest config error).")
            return
        if not data_filename or "无可用文件" in data_filename or "目录" in data_filename:
            QMessageBox.warning(self, "数据错误", "请选择一个有效的数据文件.")
            self.equity_curve_label.setText("数据文件错误 (Data file error).")
            return

        try:
            initial_cash_str = self.initial_cash_edit.text()
            initial_cash = float(initial_cash_str)
            if initial_cash <= 0:
                raise ValueError("Initial cash must be positive.")
        except ValueError as e:
            QMessageBox.warning(self, "资金错误", f"无效的初始资金: {e}")
            self.equity_curve_label.setText("资金输入错误 (Initial cash error).")
            return

        try:
            # 1. Load Strategy Config
            config = strategy_configurator.load_strategy_config(strategy_filename)
            if not config:
                QMessageBox.critical(self, "加载错误", f"无法加载策略配置: {strategy_filename}")
                self.equity_curve_label.setText("策略加载失败 (Strategy load failed).")
                return

            # 2. Load and Preprocess Data
            data_filepath = os.path.join(DATA_DIR_GUI, data_filename)
            if data_filename.endswith(".csv"):
                raw_df = data_manager.load_csv(data_filepath)
            elif data_filename.endswith(".xlsx"):
                raw_df = data_manager.load_xlsx(data_filepath)
            else:
                QMessageBox.critical(self, "文件类型错误", f"不支持的数据文件类型: {data_filename}")
                self.equity_curve_label.setText("数据类型错误 (Data type error).")
                return

            if raw_df is None:
                QMessageBox.critical(self, "加载错误", f"无法加载数据文件: {data_filename}")
                self.equity_curve_label.setText("数据加载失败 (Data load failed).")
                return

            processed_df = data_manager.preprocess_data(raw_df)
            if processed_df is None or processed_df.empty:
                QMessageBox.critical(self, "预处理错误", f"数据预处理失败: {data_filename}")
                self.equity_curve_label.setText("数据预处理失败 (Preprocessing failed).")
                return

            # 3. Get Strategy Class
            strategy_class = strategy_configurator.generate_backtrader_strategy_class(config)
            if not strategy_class:
                QMessageBox.critical(self, "策略错误", f"无法为配置生成有效的策略类: {strategy_filename}")
                self.equity_curve_label.setText("策略类生成失败 (Strategy class error).")
                return

            # 4. Run Backtest
            # run_backtest now saves plot and returns dict with 'trades_log', 'initial_cash', 'final_portfolio_value'
            backtest_results = backtesting_engine.run_backtest(
                processed_df,
                strategy_class,
                config.get('params', {}), # Ensure params exist
                initial_cash
            )

            if not backtest_results:
                QMessageBox.critical(self, "回测失败", "回测引擎未能返回结果.")
                self.equity_curve_label.setText("回测引擎失败 (Backtest engine failed).")
                return

            # 5. Display Results
            stats_report_filename = "reports/gui_backtest_stats.txt" # Specific for GUI initiated backtest
            trade_stats = reporting.calculate_trade_statistics(
                backtest_results["trades_log"],
                backtest_results["initial_cash"],
                backtest_results["final_portfolio_value"]
            )
            reporting.generate_text_report(trade_stats, filename=stats_report_filename)

            with open(stats_report_filename, 'r') as f:
                self.stats_text_edit.setText(f.read())

            # Equity curve plot is saved by run_backtest to "reports/backtest_equity_curve.png"
            equity_plot_path = os.path.join(REPORTS_DIR_GUI, "backtest_equity_curve.png")
            if os.path.exists(equity_plot_path):
                pixmap = QPixmap(equity_plot_path)
                self.equity_curve_label.setPixmap(pixmap.scaled(
                    self.equity_curve_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self.equity_curve_label.setText("未能生成图表 (Equity curve plot not found).")

            QMessageBox.information(self, "回测完成", "回测已完成. 结果已显示.")

        except Exception as e:
            QMessageBox.critical(self, "回测异常", f"执行回测时发生错误: {e}")
            self.equity_curve_label.setText(f"回测异常 (Exception): {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Ensure necessary directories exist for standalone test
    if not os.path.exists(STRATEGIES_DIR_GUI): os.makedirs(STRATEGIES_DIR_GUI)
    if not os.path.exists(DATA_DIR_GUI): os.makedirs(DATA_DIR_GUI)
    if not os.path.exists(REPORTS_DIR_GUI): os.makedirs(REPORTS_DIR_GUI)

    # Create a dummy strategy config for testing
    dummy_strat_conf = {"strategy_name": "rsi_strategy", "params": {"rsi_period": 14, "overbought_threshold": 70, "oversold_threshold": 30}}
    with open(os.path.join(STRATEGIES_DIR_GUI, "dummy_rsi_strat.json"), 'w') as f:
        json.dump(dummy_strat_conf, f)
    # Create a dummy data file for testing
    dummy_data = pd.DataFrame({
        'Timestamp': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
        'Open': [100,101,102], 'High': [103,104,103], 'Low': [99,100,101],
        'Close': [101,102,100], 'Volume': [1000,1200,1100]
    })
    dummy_data.to_csv(os.path.join(DATA_DIR_GUI, "dummy_data.csv"), index=False)


    main_widget = BacktestingTab()
    main_widget.setWindowTitle("Backtesting Tab Test")
    main_widget.setGeometry(100, 100, 1000, 700)
    main_widget.show()
    sys.exit(app.exec())
