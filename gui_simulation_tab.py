import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QTextEdit, QLineEdit, QMessageBox, QScrollArea, QGridLayout
)
from PySide6.QtGui import QPixmap, QDoubleValidator
from PySide6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import data_manager
import strategy_configurator
import simulated_trading # For SimulatedAccount and run_simulation
import reporting

STRATEGIES_DIR_GUI = strategy_configurator.STRATEGIES_DIR
DATA_DIR_GUI = "data"
REPORTS_DIR_GUI = reporting.REPORTS_DIR

class SimulationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Configuration Section ---
        config_group = QGroupBox("模拟交易配置 (Simulation Configuration)")
        config_layout = QFormLayout()

        self.strategy_file_combo = QComboBox()
        config_layout.addRow(QLabel("策略配置文件 (Strategy Config File):"), self.strategy_file_combo)

        self.data_file_combo = QComboBox()
        config_layout.addRow(QLabel("数据文件 (Data File):"), self.data_file_combo)

        self.initial_cash_edit = QLineEdit("100000.0")
        self.initial_cash_edit.setValidator(QDoubleValidator(0.0, 1.0e9, 2))
        config_layout.addRow(QLabel("初始资金 (Initial Cash):"), self.initial_cash_edit)

        button_layout = QHBoxLayout()
        self.refresh_files_button = QPushButton("刷新文件列表 (Refresh File Lists)")
        self.refresh_files_button.clicked.connect(self.populate_file_combos)
        button_layout.addWidget(self.refresh_files_button)

        self.run_simulation_button = QPushButton("开始模拟 (Start Simulation)")
        self.run_simulation_button.clicked.connect(self.execute_simulation)
        button_layout.addWidget(self.run_simulation_button)
        config_layout.addRow(button_layout)

        config_group.setLayout(config_layout)
        self.main_layout.addWidget(config_group)

        # --- Results Display Section ---
        self.results_group = QGroupBox("模拟结果 (Simulation Results)")
        results_main_layout = QVBoxLayout()

        self.stats_text_edit = QTextEdit()
        self.stats_text_edit.setReadOnly(True)
        results_main_layout.addWidget(self.stats_text_edit, 1) # Allow text edit to take some space

        # Layout for plots (side-by-side if possible, or stacked)
        plots_layout = QHBoxLayout()

        self.equity_curve_scroll = QScrollArea()
        self.equity_curve_scroll.setWidgetResizable(True)
        self.equity_curve_label = QLabel("模拟完成后将在此显示图表 (Equity curve will be displayed here after simulation.)")
        self.equity_curve_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equity_curve_label.setMinimumSize(300, 200)
        self.equity_curve_scroll.setWidget(self.equity_curve_label)
        plots_layout.addWidget(self.equity_curve_scroll, 1)

        self.positions_history_scroll = QScrollArea()
        self.positions_history_scroll.setWidgetResizable(True)
        self.positions_history_label = QLabel("模拟完成后将在此显示图表 (Positions history will be displayed here.)")
        self.positions_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.positions_history_label.setMinimumSize(300, 200)
        self.positions_history_scroll.setWidget(self.positions_history_label)
        plots_layout.addWidget(self.positions_history_scroll, 1)

        results_main_layout.addLayout(plots_layout, 2) # Allow plots to take more space
        self.results_group.setLayout(results_main_layout)
        self.main_layout.addWidget(self.results_group)
        self.main_layout.setStretchFactor(self.results_group, 1) # Allow results group to expand

        self.populate_file_combos()

    def _populate_combo_box(self, combo_box, directory, extension_filters):
        combo_box.clear()
        if not os.path.exists(directory):
            print(f"Warning: Directory '{directory}' not found for combo box.")
            combo_box.addItem(f"目录 '{directory}' 未找到")
            combo_box.setEnabled(False)
            return
        combo_box.setEnabled(True)
        files = [f for f in os.listdir(directory) if any(f.endswith(ext) for ext in extension_filters)]
        if not files: combo_box.addItem("无可用文件")
        else: combo_box.addItems(files)

    def populate_file_combos(self):
        self._populate_combo_box(self.strategy_file_combo, STRATEGIES_DIR_GUI, [".json"])
        self._populate_combo_box(self.data_file_combo, DATA_DIR_GUI, [".csv", ".xlsx"])
        self.stats_text_edit.clear()
        self.equity_curve_label.setText("请运行模拟以查看图表.")
        self.equity_curve_label.setPixmap(QPixmap())
        self.positions_history_label.setText("请运行模拟以查看图表.")
        self.positions_history_label.setPixmap(QPixmap())


    def execute_simulation(self):
        self.stats_text_edit.clear()
        self.equity_curve_label.setText("模拟运行中...")
        self.equity_curve_label.setPixmap(QPixmap())
        self.positions_history_label.setText("模拟运行中...")
        self.positions_history_label.setPixmap(QPixmap())
        QApplication.processEvents()

        strategy_filename = self.strategy_file_combo.currentText()
        data_filename = self.data_file_combo.currentText()

        # Basic validation for combo box selections
        if not strategy_filename or "无可用文件" in strategy_filename or "目录" in strategy_filename:
            QMessageBox.warning(self, "配置错误", "请选择一个有效的策略配置文件."); return
        if not data_filename or "无可用文件" in data_filename or "目录" in data_filename:
            QMessageBox.warning(self, "数据错误", "请选择一个有效的数据文件."); return

        try:
            initial_cash = float(self.initial_cash_edit.text())
            if initial_cash <= 0: raise ValueError("Initial cash must be positive.")
        except ValueError as e:
            QMessageBox.warning(self, "资金错误", f"无效的初始资金: {e}"); return

        try:
            config = strategy_configurator.load_strategy_config(strategy_filename)
            if not config: QMessageBox.critical(self, "加载错误", f"无法加载策略: {strategy_filename}"); return

            data_filepath = os.path.join(DATA_DIR_GUI, data_filename)
            raw_df = data_manager.load_csv(data_filepath) if data_filename.endswith(".csv") else data_manager.load_xlsx(data_filepath)
            if raw_df is None: QMessageBox.critical(self, "加载错误", f"无法加载数据: {data_filename}"); return

            processed_df = data_manager.preprocess_data(raw_df)
            if processed_df is None or processed_df.empty:
                QMessageBox.critical(self, "预处理错误", f"数据预处理失败: {data_filename}"); return

            # Use generate_strategy_function for simple stubs
            strategy_function = strategy_configurator.generate_strategy_function(config)
            if not strategy_function:
                QMessageBox.critical(self, "策略错误", f"无法为配置生成有效的策略函数: {strategy_filename}"); return

            account = simulated_trading.SimulatedAccount(initial_cash=initial_cash)
            symbol_name = os.path.splitext(os.path.basename(data_filename))[0].split('_')[0] # Extract symbol from filename like 'MSFT_YAHOO_...'

            sim_account_result = simulated_trading.run_simulation(
                processed_df, symbol_name, strategy_function, account
            )

            # Display Results
            stats_report_filename = os.path.join(REPORTS_DIR_GUI, "gui_simulated_stats.txt")
            final_val = sim_account_result.portfolio_value_history[-1]['value'] if sim_account_result.portfolio_value_history else sim_account_result.initial_cash

            trade_stats = reporting.calculate_trade_statistics(
                sim_account_result.trades_history,
                sim_account_result.initial_cash,
                final_val
            )
            reporting.generate_text_report(trade_stats, filename=stats_report_filename)
            with open(stats_report_filename, 'r') as f: self.stats_text_edit.setText(f.read())

            equity_plot_path = os.path.join(REPORTS_DIR_GUI, "gui_simulated_equity.png")
            reporting.plot_equity_curve(sim_account_result.portfolio_value_history,
                                        title="Simulated Equity Curve", filename=equity_plot_path)
            if os.path.exists(equity_plot_path):
                pixmap_equity = QPixmap(equity_plot_path)
                self.equity_curve_label.setPixmap(pixmap_equity.scaled(self.equity_curve_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else: self.equity_curve_label.setText("未能生成图表.")

            positions_plot_path = os.path.join(REPORTS_DIR_GUI, "gui_simulated_positions.png")
            reporting.plot_positions_history(sim_account_result.trades_history,
                                             sim_account_result.initial_cash,
                                             processed_df.index,
                                             title=f"Simulated Positions for {symbol_name}",
                                             filename=positions_plot_path)
            if os.path.exists(positions_plot_path):
                pixmap_positions = QPixmap(positions_plot_path)
                self.positions_history_label.setPixmap(pixmap_positions.scaled(self.positions_history_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else: self.positions_history_label.setText("未能生成图表.")

            QMessageBox.information(self, "模拟完成", "模拟交易已完成.")
        except Exception as e:
            QMessageBox.critical(self, "模拟异常", f"执行模拟时发生错误: {e}")
            self.equity_curve_label.setText(f"模拟异常: {e}")
            self.positions_history_label.setText("")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    if not os.path.exists(STRATEGIES_DIR_GUI): os.makedirs(STRATEGIES_DIR_GUI)
    if not os.path.exists(DATA_DIR_GUI): os.makedirs(DATA_DIR_GUI)
    if not os.path.exists(REPORTS_DIR_GUI): os.makedirs(REPORTS_DIR_GUI)

    # Ensure a functional config for simple stubs exists
    # This should be "test_rsi_config_functional.json" as per strategy_configurator.py's __main__
    # If it's missing, simulated_trading.py's main demo would fail at load_strategy_config
    # For this tab's standalone test, let's quickly make one if it doesn't exist
    functional_config_path = os.path.join(STRATEGIES_DIR_GUI, "test_rsi_config_functional.json")
    if not os.path.exists(functional_config_path):
        dummy_functional_cfg = {
            "strategy_name": "rsi_strategy",
            "params": {"rsi_period": 10, "overbought_threshold": 80.0, "oversold_threshold": 20.0},
            "description": "RSI strategy for simple stub simulation (created by gui_simulation_tab test)."
        }
        with open(functional_config_path, 'w') as f: json.dump(dummy_functional_cfg, f)
        print(f"Created dummy functional config: {functional_config_path}")

    # Create a dummy data file
    dummy_data_path = os.path.join(DATA_DIR_GUI, "dummy_sim_data.csv")
    if not os.path.exists(dummy_data_path):
        dummy_data = pd.DataFrame({
            'Timestamp': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']),
            'Open': [100,101,102,103,104], 'High': [103,104,103,105,106], 'Low': [99,100,101,102,103],
            'Close': [101,102,100,104,105], 'Volume': [1000,1200,1100,1500,1300]
        }).set_index('Timestamp')
        dummy_data.to_csv(dummy_data_path)
        print(f"Created dummy data file: {dummy_data_path}")


    main_widget = SimulationTab()
    main_widget.setWindowTitle("Simulation Tab Test")
    main_widget.setGeometry(100, 100, 1200, 800)
    main_widget.show()
    sys.exit(app.exec())
