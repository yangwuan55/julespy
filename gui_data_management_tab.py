import sys
import os
import shutil
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit,
    QComboBox, QDateEdit, QMessageBox, QFileDialog, QHeaderView
)
from PySide6.QtCore import Qt, QDate

# Ensure other modules can be imported (assuming /app is the root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import data_manager # This should now work if this file is in /app

# Define DATA_DIR here for clarity, or rely on data_manager.DATA_DIR if it's made accessible
# For now, let's assume data_manager functions correctly handle paths relative to its own DATA_DIR
# If data_manager.DATA_DIR is not a public constant, we might need to define it here too.
# Let's assume data_manager.py defines DATA_DIR = "data" at module level or handles it internally.
# For this GUI, we'll construct paths to "data/" directly.
DATA_DIR_GUI = "data"


class DataManagementTab(QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QHBoxLayout(self)

        # Left Panel: Local Files
        self.local_files_group = QGroupBox("本地数据文件 (Local Data Files)")
        local_files_layout = QVBoxLayout()

        self.files_list_widget = QListWidget()
        self.files_list_widget.currentItemChanged.connect(self.display_selected_file_data)
        local_files_layout.addWidget(self.files_list_widget)

        refresh_button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("刷新列表 (Refresh List)")
        self.refresh_button.clicked.connect(self.populate_local_files_list)
        refresh_button_layout.addWidget(self.refresh_button)

        self.import_button = QPushButton("导入文件 (Import File)")
        self.import_button.clicked.connect(self.import_data_file)
        refresh_button_layout.addWidget(self.import_button)
        local_files_layout.addLayout(refresh_button_layout)

        self.local_files_group.setLayout(local_files_layout)
        self.main_layout.addWidget(self.local_files_group, 1) # Stretch factor 1

        # Right Panel: Actions & Preview
        self.actions_group = QGroupBox("数据操作与预览 (Data Actions & Preview)")
        actions_layout = QVBoxLayout()

        # Data Preview
        self.data_preview_table = QTableWidget()
        self.data_preview_table.setColumnCount(0) # Will be set based on data
        self.data_preview_table.setRowCount(0)
        self.data_preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Read-only
        actions_layout.addWidget(self.data_preview_table, 2) # Stretch factor for table

        # Download Section
        download_group = QGroupBox("下载数据 (Download Data)")
        download_form_layout = QFormLayout()
        self.symbol_edit = QLineEdit()
        self.symbol_edit.setPlaceholderText("例如 (e.g., AAPL, BTCUSDT)")
        self.start_date_edit = QDateEdit(QDate.currentDate().addMonths(-3)) # Default 3 months ago
        self.start_date_edit.setCalendarPopup(True)
        self.end_date_edit = QDateEdit(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["yahoo", "binance"])
        self.download_button = QPushButton("开始下载 (Start Download)")
        self.download_button.clicked.connect(self.download_data_from_ui)
        download_form_layout.addRow("代码 (Symbol):", self.symbol_edit)
        download_form_layout.addRow("开始日期 (Start Date):", self.start_date_edit)
        download_form_layout.addRow("结束日期 (End Date):", self.end_date_edit)
        download_form_layout.addRow("数据源 (Source):", self.source_combo)
        download_form_layout.addRow(self.download_button)
        download_group.setLayout(download_form_layout)
        actions_layout.addWidget(download_group)

        # Preprocess Section
        self.preprocess_button = QPushButton("预处理选中文件 (Preprocess Selected File)")
        self.preprocess_button.clicked.connect(self.preprocess_selected_file)
        self.preprocess_button.setEnabled(False) # Enabled when a file is selected
        actions_layout.addWidget(self.preprocess_button)

        self.actions_group.setLayout(actions_layout)
        self.main_layout.addWidget(self.actions_group, 2) # Stretch factor 2

        self.populate_local_files_list()

    def _ensure_data_dir_exists(self):
        if not os.path.exists(DATA_DIR_GUI):
            try:
                os.makedirs(DATA_DIR_GUI)
                print(f"Created data directory: {DATA_DIR_GUI}")
            except Exception as e:
                QMessageBox.critical(self, "错误 (Error)", f"无法创建数据目录 (Could not create data directory) '{DATA_DIR_GUI}': {e}")
                return False
        return True

    def populate_local_files_list(self):
        self.files_list_widget.clear()
        self.preprocess_button.setEnabled(False)
        if not self._ensure_data_dir_exists(): return

        try:
            for filename in os.listdir(DATA_DIR_GUI):
                if filename.endswith(".csv") or filename.endswith(".xlsx"):
                    self.files_list_widget.addItem(filename)
        except Exception as e:
            QMessageBox.critical(self, "错误 (Error)", f"无法列出数据文件 (Could not list data files): {e}")


    def import_data_file(self):
        if not self._ensure_data_dir_exists(): return

        filename, _ = QFileDialog.getOpenFileName(
            self, "选择要导入的文件 (Select File to Import)", "",
            "Data Files (*.csv *.xlsx)"
        )
        if filename:
            try:
                base_filename = os.path.basename(filename)
                destination_path = os.path.join(DATA_DIR_GUI, base_filename)
                shutil.copy(filename, destination_path)
                self.populate_local_files_list()
                QMessageBox.information(self, "成功 (Success)", f"文件 '{base_filename}' 已导入到 '{DATA_DIR_GUI}'.")
            except Exception as e:
                QMessageBox.critical(self, "导入错误 (Import Error)", f"无法导入文件 (Could not import file): {e}")

    def _populate_qtablewidget(self, df, table_widget):
        table_widget.setRowCount(0) # Clear previous content
        if df is None or df.empty:
            table_widget.setColumnCount(0)
            return

        table_widget.setRowCount(min(len(df), 50)) # Display up to 50 rows
        table_widget.setColumnCount(len(df.columns))
        table_widget.setHorizontalHeaderLabels(df.columns)

        for i, (idx, row) in enumerate(df.head(50).iterrows()):
            # Display index as first column if it's meaningful (e.g. DatetimeIndex)
            # For now, let's just display row number for simplicity, or make index a column
            # table_widget.setVerticalHeaderItem(i, QTableWidgetItem(str(idx)))
            for j, col_val in enumerate(row):
                table_widget.setItem(i, j, QTableWidgetItem(str(col_val)))
        table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)


    def display_selected_file_data(self, current_item):
        if not current_item:
            self.data_preview_table.setRowCount(0)
            self.data_preview_table.setColumnCount(0)
            self.preprocess_button.setEnabled(False)
            return

        filename = current_item.text()
        full_path = os.path.join(DATA_DIR_GUI, filename)
        df = None
        try:
            if filename.endswith(".csv"):
                df = data_manager.load_csv(full_path)
            elif filename.endswith(".xlsx"):
                df = data_manager.load_xlsx(full_path)

            if df is not None:
                self._populate_qtablewidget(df, self.data_preview_table)
                self.preprocess_button.setEnabled(True)
            else:
                raise ValueError("Loaded DataFrame is None.")
        except Exception as e:
            self.data_preview_table.setRowCount(0)
            self.data_preview_table.setColumnCount(0)
            self.preprocess_button.setEnabled(False)
            QMessageBox.critical(self, "加载错误 (Load Error)", f"无法加载或解析文件 (Could not load/parse file) '{filename}': {e}")

    def download_data_from_ui(self):
        symbol = self.symbol_edit.text().strip().upper()
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
        source = self.source_combo.currentText()

        if not symbol:
            QMessageBox.warning(self, "输入错误 (Input Error)", "请输入股票/交易对代码 (Please enter a symbol).")
            return

        # Basic date validation
        if self.start_date_edit.date() >= self.end_date_edit.date():
            QMessageBox.warning(self, "日期错误 (Date Error)", "开始日期必须早于结束日期 (Start date must be before end date).")
            return

        try:
            # Show some feedback that download is in progress if it's long
            self.download_button.setText("下载中... (Downloading...)")
            self.download_button.setEnabled(False)
            QApplication.processEvents() # Update UI

            df_downloaded = data_manager.download_data(symbol, start_date, end_date, source)

            if df_downloaded is not None and not df_downloaded.empty:
                self.populate_local_files_list() # Refreshes list, which includes the new cached file
                QMessageBox.information(self, "下载成功 (Download Successful)",
                                        f"数据已下载并保存到 'data/' 目录中 (Data downloaded and saved to 'data/' directory).")
            elif df_downloaded is not None and df_downloaded.empty:
                 QMessageBox.information(self, "下载提示 (Download Info)",
                                        f"未找到数据 (No data found for {symbol} from {start_date} to {end_date} on {source}).")
            else: # df_downloaded is None
                QMessageBox.critical(self, "下载失败 (Download Failed)",
                                     "下载数据时发生错误 (An error occurred while downloading data). 检查控制台输出获取更多信息 (Check console output for details).")
        except Exception as e:
            QMessageBox.critical(self, "下载异常 (Download Exception)", f"下载过程中发生异常 (Exception during download): {e}")
        finally:
            self.download_button.setText("开始下载 (Start Download)")
            self.download_button.setEnabled(True)


    def preprocess_selected_file(self):
        current_item = self.files_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "选择错误 (Selection Error)", "请先从列表中选择一个文件 (Please select a file from the list first).")
            return

        filename = current_item.text()
        full_path = os.path.join(DATA_DIR_GUI, filename)
        df_raw = None
        try:
            if filename.endswith(".csv"):
                df_raw = data_manager.load_csv(full_path)
            elif filename.endswith(".xlsx"):
                df_raw = data_manager.load_xlsx(full_path)
            if df_raw is None: raise ValueError("Failed to load data for preprocessing.")
        except Exception as e:
            QMessageBox.critical(self, "加载错误 (Load Error)", f"预处理前无法加载文件 (Could not load file for preprocessing): {e}")
            return

        df_processed = data_manager.preprocess_data(df_raw)
        if df_processed is None or df_processed.empty:
            QMessageBox.warning(self, "预处理失败 (Preprocessing Failed)", "数据预处理未返回有效数据 (Preprocessing did not return valid data).")
            return

        # Ask user how to save
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("保存预处理数据 (Save Preprocessed Data)")
        msg_box.setText(f"文件 '{filename}' 已预处理 (File '{filename}' has been preprocessed).")
        overwrite_button = msg_box.addButton("覆盖原文件 (Overwrite)", QMessageBox.ButtonRole.AcceptRole)
        save_as_button = msg_box.addButton("另存为... (Save As...)", QMessageBox.ButtonRole.ApplyRole)
        msg_box.addButton("取消 (Cancel)", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        save_path = None
        if msg_box.clickedButton() == overwrite_button:
            save_path = full_path
        elif msg_box.clickedButton() == save_as_button:
            new_filename, _ = QFileDialog.getSaveFileName(
                self, "另存为预处理数据 (Save Preprocessed Data As)", DATA_DIR_GUI,
                "CSV Files (*.csv);;Excel Files (*.xlsx)" # Allow saving as either
            )
            if new_filename:
                save_path = new_filename
        else: # Cancelled
            return

        if save_path:
            try:
                # Save based on extension, default to CSV if not obvious
                if save_path.endswith(".xlsx"):
                    df_processed.to_excel(save_path, index=True) # Preprocessed data has Timestamp index
                else: # Default to CSV
                    if not save_path.endswith(".csv"): save_path += ".csv"
                    df_processed.to_csv(save_path, index=True) # Preprocessed data has Timestamp index

                QMessageBox.information(self, "保存成功 (Save Successful)", f"预处理后的数据已保存到 (Preprocessed data saved to):\n{save_path}")
                self.populate_local_files_list()
                # Optionally, select and display the newly saved/overwritten file
                items = self.files_list_widget.findItems(os.path.basename(save_path), Qt.MatchFlag.MatchExactly)
                if items: self.files_list_widget.setCurrentItem(items[0])
                else: self.display_selected_file_data(None) # Clear preview if new name not found

            except Exception as e:
                QMessageBox.critical(self, "保存失败 (Save Failed)", f"无法保存预处理数据 (Could not save preprocessed data): {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Ensure data directory exists for standalone test
    if not os.path.exists(DATA_DIR_GUI):
        os.makedirs(DATA_DIR_GUI)
        print(f"Created directory: {DATA_DIR_GUI} for demo.")
        # Create a dummy file for testing list population and display
        try:
            dummy_df_for_test = pd.DataFrame({'A': [1,2], 'B': [3,4]})
            dummy_df_for_test.to_csv(os.path.join(DATA_DIR_GUI, "dummy_test_data.csv"), index=False)
        except Exception as e:
            print(f"Could not create dummy test file: {e}")


    main_widget = DataManagementTab()
    main_widget.setWindowTitle("Data Management Tab Test")
    main_widget.setGeometry(100, 100, 800, 600)
    main_widget.show()
    sys.exit(app.exec())
