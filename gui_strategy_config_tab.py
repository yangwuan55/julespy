import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox,
    QFormLayout, QLineEdit, QPushButton, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

# Add parent directory to sys.path to allow importing strategy_configurator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # This assumes strategy_configurator.py is in the parent directory (e.g., /app)
    # when gui_strategy_config_tab.py might be in a subfolder like /app/gui_tabs
    # For a flat structure (/app/gui_strategy_config_tab.py and /app/strategy_configurator.py),
    # direct import should work if PYTHONPATH or execution context is /app.
    # The sys.path.append above tries to handle this.
    import strategy_configurator
except ModuleNotFoundError:
    # Fallback for flatter structure if the above doesn't work directly in some exec environments
    # This usually happens if the script is run from a different CWD.
    # For the current tool environment, /app is the CWD.
    if os.path.basename(os.getcwd()) == "app": # if CWD is /app
         import strategy_configurator
    else: # If script is in /app and CWD is /
         from app import strategy_configurator


class StrategyConfigTab(QWidget):
    def __init__(self):
        super().__init__()
        self.param_inputs = {}  # To store QLineEdit widgets for parameters

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


        # 1. Strategy Template Selection
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("选择策略模板 (Select Strategy Template):"))
        self.template_combo = QComboBox()

        # Populate with display names, store internal key as well if needed
        self.template_display_names = {
            key: details["display_name"]
            for key, details in strategy_configurator.STRATEGY_TEMPLATES.items()
        }
        self.template_internal_names = {
            details["display_name"]: key
            for key, details in strategy_configurator.STRATEGY_TEMPLATES.items()
        }

        self.template_combo.addItems(list(self.template_display_names.values()))
        self.template_combo.currentTextChanged.connect(self.update_parameters_ui_from_display_name)
        selection_layout.addWidget(self.template_combo)
        main_layout.addLayout(selection_layout)

        # 2. Parameters Area
        self.params_groupbox = QGroupBox("策略参数 (Strategy Parameters)")
        self.params_form_layout = QFormLayout()
        self.params_groupbox.setLayout(self.params_form_layout)
        main_layout.addWidget(self.params_groupbox)

        # 3. Action Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("保存策略 (Save Strategy)")
        self.save_button.clicked.connect(self.save_strategy)
        button_layout.addWidget(self.save_button)

        self.load_button = QPushButton("加载策略 (Load Strategy)")
        self.load_button.clicked.connect(self.load_strategy)
        button_layout.addWidget(self.load_button)
        main_layout.addLayout(button_layout)

        # Initial UI update
        if self.template_combo.count() > 0:
            self.update_parameters_ui_from_display_name(self.template_combo.currentText())
        else:
            # Handle case with no templates (though STRATEGY_TEMPLATES should not be empty)
            self.params_form_layout.addRow(QLabel("No strategy templates available."))


    def update_parameters_ui_from_display_name(self, display_name):
        internal_name = self.template_internal_names.get(display_name)
        if internal_name:
            self.update_parameters_ui(internal_name)

    def update_parameters_ui(self, template_key=None):
        # Clear existing parameter widgets
        while self.params_form_layout.rowCount() > 0:
            self.params_form_layout.removeRow(0)
        self.param_inputs.clear()

        if template_key is None: # Should be called by _from_display_name
            current_display_name = self.template_combo.currentText()
            template_key = self.template_internal_names.get(current_display_name)

        if not template_key:
            self.params_form_layout.addRow(QLabel("Please select a valid template."))
            return

        template_details = strategy_configurator.STRATEGY_TEMPLATES.get(template_key)
        if not template_details:
            self.params_form_layout.addRow(QLabel(f"Template '{template_key}' not found."))
            return

        for param_name, param_info in template_details["params"].items():
            label = QLabel(f"{param_name} ({param_info['type'].__name__}):")
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(param_info.get("prompt", ""))
            self.params_form_layout.addRow(label, line_edit)
            self.param_inputs[param_name] = line_edit

    def save_strategy(self):
        current_display_name = self.template_combo.currentText()
        template_key = self.template_internal_names.get(current_display_name)

        if not template_key:
            QMessageBox.warning(self, "保存错误 (Save Error)", "请选择一个有效的策略模板 (Please select a valid strategy template).")
            return

        config_params = {}
        template_details = strategy_configurator.STRATEGY_TEMPLATES[template_key]

        try:
            for param_name, line_edit_widget in self.param_inputs.items():
                value_str = line_edit_widget.text()
                param_type = template_details["params"][param_name]["type"]
                if not value_str and param_type is not str: # Allow empty string for str type
                    raise ValueError(f"参数 '{param_name}' 不能为空 (Parameter '{param_name}' cannot be empty).")

                if param_type == int:
                    config_params[param_name] = int(value_str)
                elif param_type == float:
                    config_params[param_name] = float(value_str)
                else: # str or other
                    config_params[param_name] = value_str
        except ValueError as e:
            QMessageBox.warning(self, "参数错误 (Parameter Error)", f"无效的参数值 (Invalid parameter value): {e}")
            return

        strategy_config_dict = {
            "strategy_name": template_key,
            "params": config_params,
            # Optionally add display name or other meta info
            "display_name": current_display_name
        }

        # Default directory is STRATEGIES_DIR from strategy_configurator
        # Ensure strategy_configurator.STRATEGIES_DIR is accessible or pass it
        strategies_dir_path = os.path.join(os.path.dirname(strategy_configurator.__file__), strategy_configurator.STRATEGIES_DIR)
        if not os.path.exists(strategies_dir_path):
             os.makedirs(strategies_dir_path) # Ensure it exists if strategy_configurator hasn't created it

        filename, _ = QFileDialog.getSaveFileName(
            self, "保存策略配置文件 (Save Strategy Configuration File)",
            strategies_dir_path,  # Default directory
            "JSON Files (*.json)"
        )

        if filename:
            # QFileDialog returns full path, strategy_configurator.save_strategy_config expects just filename
            # if its STRATEGIES_DIR is used internally. Let's pass the full path to be safe.
            # Correction: save_strategy_config expects a base filename and uses its own STRATEGIES_DIR.
            # So, we need to make sure the path is relative to STRATEGIES_DIR or pass only basename.

            # If filename is within strategies_dir_path, get relative path
            if filename.startswith(strategies_dir_path + os.sep):
                filename_to_save = os.path.relpath(filename, strategies_dir_path)
            else: # If user selected outside, this might be an issue or save it as absolute
                  # For now, let's try to save it using strategy_configurator's logic by providing basename
                filename_to_save = os.path.basename(filename)


            saved_path = strategy_configurator.save_strategy_config(strategy_config_dict, filename_to_save)
            if saved_path:
                QMessageBox.information(self, "保存成功 (Save Successful)", f"策略已保存到 (Strategy saved to):\n{saved_path}")
            else:
                QMessageBox.critical(self, "保存失败 (Save Failed)", "无法保存策略配置 (Could not save strategy configuration).")
        else:
            QMessageBox.information(self, "保存取消 (Save Cancelled)", "保存操作已取消 (Save operation cancelled).")


    def load_strategy(self):
        strategies_dir_path = os.path.join(os.path.dirname(strategy_configurator.__file__), strategy_configurator.STRATEGIES_DIR)

        filename, _ = QFileDialog.getOpenFileName(
            self, "加载策略配置文件 (Load Strategy Configuration File)",
            strategies_dir_path,
            "JSON Files (*.json)"
        )

        if filename:
            # Similar to save, load_strategy_config expects filename relative to its STRATEGIES_DIR
            if filename.startswith(strategies_dir_path + os.sep):
                filename_to_load = os.path.relpath(filename, strategies_dir_path)
            else:
                # This case is tricky; if file is outside, load_strategy_config might not find it
                # For now, assume user selects from the default dir, then basename is fine
                filename_to_load = os.path.basename(filename)

            loaded_config = strategy_configurator.load_strategy_config(filename_to_load)
            if loaded_config:
                strategy_name = loaded_config.get("strategy_name")
                params = loaded_config.get("params", {})

                # Find display name corresponding to strategy_name (internal key)
                display_name_to_set = None
                for key, details in strategy_configurator.STRATEGY_TEMPLATES.items():
                    if key == strategy_name:
                        display_name_to_set = details["display_name"]
                        break

                if display_name_to_set:
                    self.template_combo.setCurrentText(display_name_to_set)
                    # update_parameters_ui will be called by currentTextChanged signal
                    # Then populate the values:
                    for param_name, value in params.items():
                        if param_name in self.param_inputs:
                            self.param_inputs[param_name].setText(str(value))
                    QMessageBox.information(self, "加载成功 (Load Successful)", f"策略 '{display_name_to_set}' 已加载 (Strategy '{display_name_to_set}' loaded).")
                else:
                    QMessageBox.warning(self, "加载错误 (Load Error)", f"未知的策略类型 '{strategy_name}' 在配置文件中 (Unknown strategy type '{strategy_name}' in config file).")
            else:
                QMessageBox.critical(self, "加载失败 (Load Failed)", "无法加载策略配置 (Could not load strategy configuration).")
        else:
             QMessageBox.information(self, "加载取消 (Load Cancelled)", "加载操作已取消 (Load operation cancelled).")


if __name__ == '__main__':
    # This part is for standalone testing of the tab widget
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    # Ensure strategy_configurator.py has run once to create dummy configs if needed by load test
    # Or handle it gracefully in load test.

    main_widget = StrategyConfigTab()
    main_widget.setWindowTitle("Strategy Config Tab Test")
    main_widget.setGeometry(100, 100, 500, 400)
    main_widget.show()
    sys.exit(app.exec())
