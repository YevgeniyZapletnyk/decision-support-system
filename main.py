from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from analytics_service import AnalyticsService, ExpertAggregationService
from database import Database


APP_TITLE = "СППР вибору ноутбука"


class DSSApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1400x900")
        self.minsize(1200, 760)

        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        mongo_db = os.getenv("MONGODB_DB", "decision_support_system_tkinter")
        self.db = Database(uri=mongo_uri, db_name=mongo_db)
        self.analytics = AnalyticsService()

        self._build_layout()
        self.refresh_all()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 18, "bold")
                  ).grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Готово до роботи")
        ttk.Label(top, textvariable=self.status_var).grid(
            row=0, column=1, sticky="e")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew",
                           padx=10, pady=(0, 10))

        self.tab_expert = ttk.Frame(self.notebook, padding=10)
        self.tab_model = ttk.Frame(self.notebook, padding=10)
        self.tab_rules = ttk.Frame(self.notebook, padding=10)
        self.tab_results = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_expert, text="Експертиза")
        self.notebook.add(self.tab_model, text="Модель та Дані")
        self.notebook.add(self.tab_rules, text="Експертна логіка")
        self.notebook.add(self.tab_results, text="Результати та Аналіз")

        self._build_expert_tab()
        self._build_model_tab()
        self._build_rules_tab()
        self._build_results_tab()

    def _build_expert_tab(self) -> None:
        frame = self.tab_expert
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        intro = (
            "Імпорт експертних ваг із CSV або прямого посилання на CSV з Google Sheets. "
            "Назви стовпців повинні збігатися з назвами критеріїв, рядків має бути не менше 7."
        )
        ttk.Label(frame, text=intro, wraplength=900, justify="left").grid(
            row=0, column=0, sticky="w")

        control = ttk.LabelFrame(
            frame, text="Імпорт ваг критеріїв", padding=10)
        control.grid(row=1, column=0, sticky="ew", pady=10)
        control.columnconfigure(1, weight=1)

        ttk.Label(control, text="CSV файл або URL:").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self.expert_source_var = tk.StringVar()
        ttk.Entry(control, textvariable=self.expert_source_var).grid(
            row=0, column=1, sticky="ew")
        ttk.Button(control, text="Огляд", command=self._browse_csv).grid(
            row=0, column=2, padx=8)

        ttk.Label(control, text="Метод узгодження:").grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        self.expert_method_var = tk.StringVar(value="mean")
        ttk.Combobox(
            control,
            textvariable=self.expert_method_var,
            state="readonly",
            values=list(ExpertAggregationService.METHODS.keys()),
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Button(control, text="Імпортувати", command=self.import_expert_weights).grid(
            row=1, column=2, pady=(8, 0))

        self.expert_text = tk.Text(frame, wrap="word", height=24)
        self.expert_text.grid(row=2, column=0, sticky="nsew")

    def _build_model_tab(self) -> None:
        frame = self.tab_model
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        alt_box = ttk.LabelFrame(frame, text="Альтернативи", padding=10)
        alt_box.grid(row=0, column=0, sticky="nsew",
                     padx=(0, 6), pady=(0, 6), rowspan=2)
        alt_box.columnconfigure(1, weight=1)
        alt_box.rowconfigure(3, weight=1)

        self.alt_name_var = tk.StringVar()
        self.alt_desc_var = tk.StringVar()
        ttk.Label(alt_box, text="Назва").grid(row=0, column=0, sticky="w")
        ttk.Entry(alt_box, textvariable=self.alt_name_var).grid(
            row=0, column=1, sticky="ew")
        ttk.Label(alt_box, text="Опис").grid(row=1, column=0, sticky="w")
        ttk.Entry(alt_box, textvariable=self.alt_desc_var).grid(
            row=1, column=1, sticky="ew")
        ttk.Button(alt_box, text="Додати / оновити", command=self.save_alternative).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=6)
        self.alternatives_tree = self._treeview(
            alt_box, ["name", "description"], ["Назва", "Опис"])
        self.alternatives_tree.grid(
            row=3, column=0, columnspan=2, sticky="nsew")
        self.alternatives_tree.bind(
            "<<TreeviewSelect>>", self.fill_selected_alternative)
        ttk.Button(alt_box, text="Видалити", command=self.delete_alternative).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        crit_box = ttk.LabelFrame(frame, text="Критерії", padding=10)
        crit_box.grid(row=0, column=1, sticky="nsew",
                      padx=(6, 0), pady=(0, 6), rowspan=2)
        crit_box.columnconfigure(1, weight=1)
        crit_box.rowconfigure(5, weight=1)

        self.crit_name_var = tk.StringVar()
        self.crit_type_var = tk.StringVar(value="maximize")
        self.crit_desc_var = tk.StringVar()
        self.crit_weight_var = tk.StringVar(value="0.1")

        ttk.Label(crit_box, text="Назва").grid(row=0, column=0, sticky="w")
        ttk.Entry(crit_box, textvariable=self.crit_name_var).grid(
            row=0, column=1, sticky="ew")
        ttk.Label(crit_box, text="Тип").grid(row=1, column=0, sticky="w")
        ttk.Combobox(crit_box, textvariable=self.crit_type_var, values=[
                     "maximize", "minimize"], state="readonly").grid(row=1, column=1, sticky="ew")
        ttk.Label(crit_box, text="Опис").grid(row=2, column=0, sticky="w")
        ttk.Entry(crit_box, textvariable=self.crit_desc_var).grid(
            row=2, column=1, sticky="ew")
        ttk.Label(crit_box, text="Вага").grid(row=3, column=0, sticky="w")
        ttk.Entry(crit_box, textvariable=self.crit_weight_var).grid(
            row=3, column=1, sticky="ew")
        ttk.Button(crit_box, text="Додати / оновити", command=self.save_criterion).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=6)
        self.criteria_tree = self._treeview(
            crit_box, ["name", "type", "weight", "description"], ["Назва", "Тип", "Вага", "Опис"])
        self.criteria_tree.grid(row=5, column=0, columnspan=2, sticky="nsew")
        self.criteria_tree.bind("<<TreeviewSelect>>",
                                self.fill_selected_criterion)
        ttk.Button(crit_box, text="Видалити", command=self.delete_criterion).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        eval_box = ttk.LabelFrame(frame, text="Оцінки та матриця", padding=10)
        eval_box.grid(row=2, column=0, columnspan=2,
                      sticky="nsew", pady=(6, 0))
        eval_box.columnconfigure(0, weight=1)
        eval_box.rowconfigure(2, weight=1)

        form = ttk.Frame(eval_box)
        form.grid(row=0, column=0, sticky="ew")
        self.eval_alt_var = tk.StringVar()
        self.eval_crit_var = tk.StringVar()
        self.eval_value_var = tk.StringVar()
        ttk.Label(form, text="Альтернатива").grid(row=0, column=0, sticky="w")
        self.eval_alt_combo = ttk.Combobox(
            form, textvariable=self.eval_alt_var, state="readonly")
        self.eval_alt_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Label(form, text="Критерій").grid(row=0, column=1, sticky="w")
        self.eval_crit_combo = ttk.Combobox(
            form, textvariable=self.eval_crit_var, state="readonly")
        self.eval_crit_combo.grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ttk.Label(form, text="Значення").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.eval_value_var, width=16).grid(
            row=1, column=2, sticky="ew", padx=(0, 6))
        ttk.Button(form, text="Зберегти оцінку", command=self.save_evaluation).grid(
            row=1, column=3, sticky="ew")
        ttk.Button(form, text="Тестові дані", command=self.seed_sample_data).grid(
            row=1, column=4, sticky="ew", padx=(6, 0))

        self.matrix_tree = ttk.Treeview(eval_box, show="headings")
        self.matrix_tree.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

    def _build_rules_tab(self) -> None:
        frame = self.tab_rules
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        thr_box = ttk.LabelFrame(frame, text="Порогові значення", padding=10)
        thr_box.grid(row=0, column=0, sticky="nsew",
                     padx=(0, 6), pady=(0, 6), rowspan=2)
        thr_box.columnconfigure(1, weight=1)
        thr_box.rowconfigure(3, weight=1)

        self.threshold_criterion_var = tk.StringVar()
        self.threshold_value_var = tk.StringVar()
        ttk.Label(thr_box, text="Критерій").grid(row=0, column=0, sticky="w")
        self.threshold_combo = ttk.Combobox(
            thr_box, textvariable=self.threshold_criterion_var, state="readonly")
        self.threshold_combo.grid(row=0, column=1, sticky="ew")
        ttk.Label(thr_box, text="Граничне значення").grid(
            row=1, column=0, sticky="w")
        ttk.Entry(thr_box, textvariable=self.threshold_value_var).grid(
            row=1, column=1, sticky="ew")
        ttk.Button(thr_box, text="Зберегти поріг", command=self.save_threshold).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=6)
        self.thresholds_tree = self._treeview(
            thr_box, ["criterion", "value"], ["Критерій", "Поріг"])
        self.thresholds_tree.grid(row=3, column=0, columnspan=2, sticky="nsew")
        ttk.Button(thr_box, text="Видалити поріг", command=self.delete_threshold).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        rule_box = ttk.LabelFrame(frame, text="Правила IF–THEN", padding=10)
        rule_box.grid(row=0, column=1, sticky="nsew",
                      padx=(6, 0), pady=(0, 6), rowspan=2)
        rule_box.columnconfigure(1, weight=1)
        rule_box.rowconfigure(6, weight=1)

        self.rule_name_var = tk.StringVar()
        self.rule_criterion_var = tk.StringVar()
        self.rule_operator_var = tk.StringVar(value=">=")
        self.rule_condition_var = tk.StringVar()
        self.rule_action_var = tk.StringVar(value="bonus")
        self.rule_action_value_var = tk.StringVar(value="0.05")

        labels = ["Назва", "Критерій", "Оператор",
                  "Умова", "Дія", "Значення дії"]
        for idx, label in enumerate(labels):
            ttk.Label(rule_box, text=label).grid(row=idx, column=0, sticky="w")
        ttk.Entry(rule_box, textvariable=self.rule_name_var).grid(
            row=0, column=1, sticky="ew")
        self.rule_criterion_combo = ttk.Combobox(
            rule_box, textvariable=self.rule_criterion_var, state="readonly")
        self.rule_criterion_combo.grid(row=1, column=1, sticky="ew")
        ttk.Combobox(rule_box, textvariable=self.rule_operator_var, values=[
                     ">=", "<=", ">", "<", "=="], state="readonly").grid(row=2, column=1, sticky="ew")
        ttk.Entry(rule_box, textvariable=self.rule_condition_var).grid(
            row=3, column=1, sticky="ew")
        ttk.Combobox(rule_box, textvariable=self.rule_action_var, values=[
                     "bonus", "penalty", "exclude"], state="readonly").grid(row=4, column=1, sticky="ew")
        ttk.Entry(rule_box, textvariable=self.rule_action_value_var).grid(
            row=5, column=1, sticky="ew")
        ttk.Button(rule_box, text="Додати правило", command=self.save_rule).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=6)
        self.rules_tree = self._treeview(rule_box, ["name", "criterion", "condition", "action"], [
                                         "Назва", "Критерій", "Умова", "Дія"])
        self.rules_tree.grid(row=7, column=0, columnspan=2, sticky="nsew")
        ttk.Button(rule_box, text="Видалити правило", command=self.delete_rule).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _build_results_tab(self) -> None:
        frame = self.tab_results
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)
        frame.rowconfigure(3, weight=1)

        control = ttk.LabelFrame(
            frame, text="Налаштування аналізу", padding=10)
        control.grid(row=0, column=0, columnspan=2, sticky="ew")
        control.columnconfigure(1, weight=1)
        control.columnconfigure(3, weight=1)

        self.strategy_var = tk.StringVar(value="1")
        self.scenario_var = tk.StringVar(value="(базовий)")
        self.sensitivity_criterion_var = tk.StringVar()
        self.sensitivity_percent_var = tk.StringVar(value="0.2")

        ttk.Label(control, text="Метод згортки").grid(
            row=0, column=0, sticky="w")
        ttk.Combobox(control, textvariable=self.strategy_var, state="readonly", values=[
                     "1", "2", "3"]).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Label(control, text="Сценарій").grid(row=0, column=2, sticky="w")
        self.scenario_combo = ttk.Combobox(
            control, textvariable=self.scenario_var, state="readonly")
        self.scenario_combo.grid(row=0, column=3, sticky="ew")

        ttk.Label(control, text="Критерій для чутливості").grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        self.sensitivity_combo = ttk.Combobox(
            control, textvariable=self.sensitivity_criterion_var, state="readonly")
        self.sensitivity_combo.grid(
            row=1, column=1, sticky="ew", padx=(0, 10), pady=(8, 0))
        ttk.Label(control, text="Δ ваги (напр. 0.2 = 20%)").grid(
            row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(control, textvariable=self.sensitivity_percent_var).grid(
            row=1, column=3, sticky="ew", pady=(8, 0))

        action_row = ttk.Frame(frame)
        action_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        for i in range(5):
            action_row.columnconfigure(i, weight=1)
        ttk.Button(action_row, text="Запустити аналіз", command=self.run_analysis).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(action_row, text="Порівняти методи", command=self.compare_methods).grid(
            row=0, column=1, sticky="ew", padx=6)
        ttk.Button(action_row, text="Аналіз чутливості", command=self.run_sensitivity).grid(
            row=0, column=2, sticky="ew", padx=6)
        ttk.Button(action_row, text="Зберегти сценарій", command=self.save_scenario).grid(
            row=0, column=3, sticky="ew", padx=6)
        ttk.Button(action_row, text="Видалити сценарій", command=self.delete_scenario).grid(
            row=0, column=4, sticky="ew", padx=(6, 0))

        self.results_tree = self._treeview(frame, ["rank", "alternative", "score", "base_score", "rules"], [
                                           "Місце", "Альтернатива", "Фінальна оцінка", "Базова оцінка", "Правила"])
        self.results_tree.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        self.compare_tree = self._treeview(frame, ["strategy", "winner", "score"], [
                                           "Метод", "Переможець", "Оцінка"])
        self.compare_tree.grid(row=2, column=1, sticky="nsew", padx=(6, 0))
        self.analysis_text = tk.Text(frame, wrap="word")
        self.analysis_text.grid(
            row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))

    def _treeview(self, parent, columns, headings):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=140, anchor="w")
        scrollbar = ttk.Scrollbar(
            parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def _browse_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            self.expert_source_var.set(path)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def refresh_all(self) -> None:
        try:
            self.db.ping()
        except Exception as exc:
            self.set_status("MongoDB недоступна")
            messagebox.showwarning(
                "MongoDB",
                "Не вдалося підключитися до MongoDB. Запустіть локальний сервер MongoDB або перевірте MONGODB_URI.\n\n"
                f"Деталі: {exc}",
            )
            return
        self.refresh_alternatives()
        self.refresh_criteria()
        self.refresh_matrix()
        self.refresh_thresholds()
        self.refresh_rules()
        self.refresh_scenarios()
        self.set_status("Дані оновлено")

    def refresh_alternatives(self) -> None:
        for item in self.alternatives_tree.get_children():
            self.alternatives_tree.delete(item)
        self.alternatives_cache = self.db.get_alternatives()
        for alt in self.alternatives_cache:
            self.alternatives_tree.insert("", "end", iid=str(
                alt["_id"]), values=(alt["name"], alt.get("description", "")))
        self.eval_alt_combo["values"] = [
            f"{alt['name']}|{alt['_id']}" for alt in self.alternatives_cache]

    def refresh_criteria(self) -> None:
        for item in self.criteria_tree.get_children():
            self.criteria_tree.delete(item)
        self.criteria_cache = self.db.get_criteria()
        for crit in self.criteria_cache:
            self.criteria_tree.insert(
                "",
                "end",
                iid=str(crit["_id"]),
                values=(crit["name"], crit["type"], f"{float(crit.get('weight', 0)):.3f}", crit.get(
                    "description", "")),
            )
        combo_values = [f"{c['name']}|{c['_id']}" for c in self.criteria_cache]
        self.eval_crit_combo["values"] = combo_values
        self.threshold_combo["values"] = combo_values
        self.rule_criterion_combo["values"] = combo_values
        self.sensitivity_combo["values"] = combo_values

    def refresh_matrix(self) -> None:
        criteria, matrix = self.db.get_evaluation_matrix()
        columns = ["alternative_name"] + [str(c["_id"]) for c in criteria]
        self.matrix_tree.configure(columns=columns, show="headings")
        self.matrix_tree.heading("alternative_name", text="Альтернатива")
        self.matrix_tree.column("alternative_name", width=200)
        for c in criteria:
            cid = str(c["_id"])
            self.matrix_tree.heading(cid, text=c["name"])
            self.matrix_tree.column(cid, width=130)
        for item in self.matrix_tree.get_children():
            self.matrix_tree.delete(item)
        for row in matrix:
            values = [row["alternative_name"]] + \
                [row.get(c["name"], "") for c in criteria]
            self.matrix_tree.insert("", "end", values=values)

    def refresh_thresholds(self) -> None:
        thresholds = self.db.get_thresholds()
        criteria_map = {str(c["_id"]): c["name"] for c in self.criteria_cache}
        for item in self.thresholds_tree.get_children():
            self.thresholds_tree.delete(item)
        for thr in thresholds:
            self.thresholds_tree.insert("", "end", iid=thr["criterion_id"], values=(
                criteria_map.get(thr["criterion_id"], thr["criterion_id"]), thr["value"]))

    def refresh_rules(self) -> None:
        criteria_map = {str(c["_id"]): c["name"] for c in self.criteria_cache}
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)
        for rule in self.db.get_rules():
            condition = f"{rule['operator']} {rule['condition_value']}"
            action = f"{rule['action']} {rule['action_value']}"
            self.rules_tree.insert("", "end", iid=str(rule["_id"]), values=(
                rule["name"], criteria_map.get(rule["criterion_id"], rule["criterion_id"]), condition, action))

    def refresh_scenarios(self) -> None:
        scenarios = self.db.get_scenarios()
        values = ["(базовий)"] + [scenario["name"] for scenario in scenarios]
        self.scenario_combo["values"] = values
        if not self.scenario_var.get():
            self.scenario_var.set("(базовий)")

    def fill_selected_alternative(self, _event=None) -> None:
        selected = self.alternatives_tree.selection()
        if not selected:
            return
        alt = next((a for a in self.alternatives_cache if str(
            a["_id"]) == selected[0]), None)
        if alt:
            self.alt_name_var.set(alt["name"])
            self.alt_desc_var.set(alt.get("description", ""))

    def fill_selected_criterion(self, _event=None) -> None:
        selected = self.criteria_tree.selection()
        if not selected:
            return
        crit = next((c for c in self.criteria_cache if str(
            c["_id"]) == selected[0]), None)
        if crit:
            self.crit_name_var.set(crit["name"])
            self.crit_type_var.set(crit["type"])
            self.crit_desc_var.set(crit.get("description", ""))
            self.crit_weight_var.set(str(crit.get("weight", 0)))

    def save_alternative(self) -> None:
        try:
            selected = self.alternatives_tree.selection()
            if selected:
                self.db.update_alternative(
                    selected[0], self.alt_name_var.get(), self.alt_desc_var.get())
            else:
                self.db.add_alternative(
                    self.alt_name_var.get(), self.alt_desc_var.get())
            self.alt_name_var.set("")
            self.alt_desc_var.set("")
            self.refresh_alternatives()
            self.refresh_matrix()
            self.set_status("Альтернативу збережено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def delete_alternative(self) -> None:
        selected = self.alternatives_tree.selection()
        if not selected:
            return
        self.db.delete_alternative(selected[0])
        self.refresh_alternatives()
        self.refresh_matrix()
        self.set_status("Альтернативу видалено")

    def save_criterion(self) -> None:
        try:
            weight = float(self.crit_weight_var.get().replace(",", "."))
            selected = self.criteria_tree.selection()
            if selected:
                self.db.update_criterion(selected[0], self.crit_name_var.get(
                ), self.crit_type_var.get(), self.crit_desc_var.get(), weight)
            else:
                self.db.add_criterion(self.crit_name_var.get(
                ), self.crit_type_var.get(), self.crit_desc_var.get(), weight)
            self.crit_name_var.set("")
            self.crit_desc_var.set("")
            self.crit_weight_var.set("0.1")
            self.refresh_criteria()
            self.refresh_matrix()
            self.refresh_thresholds()
            self.refresh_rules()
            self.refresh_scenarios()
            self.set_status("Критерій збережено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def delete_criterion(self) -> None:
        selected = self.criteria_tree.selection()
        if not selected:
            return
        self.db.delete_criterion(selected[0])
        self.refresh_criteria()
        self.refresh_matrix()
        self.refresh_thresholds()
        self.refresh_rules()
        self.refresh_scenarios()
        self.set_status("Критерій видалено")

    def save_evaluation(self) -> None:
        try:
            alt_id = self.eval_alt_var.get().split("|")[-1]
            crit_id = self.eval_crit_var.get().split("|")[-1]
            value = float(self.eval_value_var.get().replace(",", "."))
            self.db.add_evaluation(alt_id, crit_id, value)
            self.eval_value_var.set("")
            self.refresh_matrix()
            self.set_status("Оцінку збережено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def save_threshold(self) -> None:
        try:
            criterion_id = self.threshold_criterion_var.get().split("|")[-1]
            value = float(self.threshold_value_var.get().replace(",", "."))
            self.db.upsert_threshold(criterion_id, value)
            self.refresh_thresholds()
            self.set_status("Поріг збережено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def delete_threshold(self) -> None:
        selected = self.thresholds_tree.selection()
        if not selected:
            return
        self.db.delete_threshold(selected[0])
        self.refresh_thresholds()
        self.set_status("Поріг видалено")

    def save_rule(self) -> None:
        try:
            criterion_id = self.rule_criterion_var.get().split("|")[-1]
            condition_value = float(
                self.rule_condition_var.get().replace(",", "."))
            action_value = float(
                self.rule_action_value_var.get().replace(",", "."))
            self.db.add_rule(
                name=self.rule_name_var.get(),
                criterion_id=criterion_id,
                operator=self.rule_operator_var.get(),
                condition_value=condition_value,
                action=self.rule_action_var.get(),
                action_value=action_value,
            )
            self.refresh_rules()
            self.set_status("Правило додано")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def delete_rule(self) -> None:
        selected = self.rules_tree.selection()
        if not selected:
            return
        self.db.delete_rule(selected[0])
        self.refresh_rules()
        self.set_status("Правило видалено")

    def import_expert_weights(self) -> None:
        try:
            normalized = self.db.import_expert_weights_from_csv(
                self.expert_source_var.get(), self.expert_method_var.get())
            self.refresh_criteria()
            lines = [
                f"Імпорт завершено методом: {ExpertAggregationService.METHODS[self.expert_method_var.get()]}", "\nНормалізовані ваги:"]
            criteria_map = {str(c["_id"]): c["name"]
                            for c in self.criteria_cache}
            for criterion_id, weight in normalized.items():
                lines.append(
                    f"- {criteria_map.get(criterion_id, criterion_id)}: {weight:.4f}")
            self.expert_text.delete("1.0", "end")
            self.expert_text.insert("1.0", "\n".join(lines))
            self.set_status("Експертні ваги імпортовано")
        except Exception as exc:
            messagebox.showerror("Помилка імпорту", str(exc))

    def _selected_scenario_weights(self):
        name = self.scenario_var.get()
        if name == "(базовий)":
            return None
        for scenario in self.db.get_scenarios():
            if scenario["name"] == name:
                return scenario.get("weights", {})
        return None

    def run_analysis(self) -> None:
        try:
            criteria, payload = self.db.get_analytics_payload()
            result = self.analytics.evaluate(
                criteria,
                payload,
                self.strategy_var.get(),
                thresholds=self.db.get_thresholds(),
                rules=self.db.get_rules(),
                scenario_weights=self._selected_scenario_weights(),
            )
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            for index, row in enumerate(result["results"], start=1):
                rules_text = ", ".join(
                    rule["action"] for rule in row["applied_rules"]) if row["applied_rules"] else "-"
                self.results_tree.insert("", "end", values=(
                    index, row["alternative_name"], f"{row['score']:.6f}", f"{row['base_score']:.6f}", rules_text))

            text_lines = [
                f"Стратегія: {result['strategy_name']}",
                f"Найкраща альтернатива: {result['best']['alternative_name']}",
                f"Пояснення: {result['explanation']}",
                "\nНормовані ваги:",
            ]
            for criterion in result["criteria"]:
                text_lines.append(
                    f"- {criterion['name']} ({criterion['type']}): {criterion['normalized_weight']:.4f}")
            if result["threshold_log"]:
                text_lines.append("\nПорогова обробка:")
                text_lines.extend(
                    f"- {item}" for item in result["threshold_log"])
            if result["best"].get("applied_rules"):
                text_lines.append("\nЗастосовані правила до переможця:")
                text_lines.extend(
                    f"- {rule['reason']}" for rule in result["best"]["applied_rules"])

            self.analysis_text.delete("1.0", "end")
            self.analysis_text.insert("1.0", "\n".join(text_lines))
            self.set_status("Аналіз виконано")
        except Exception as exc:
            messagebox.showerror("Помилка аналізу", str(exc))

    def compare_methods(self) -> None:
        try:
            criteria, payload = self.db.get_analytics_payload()
            comparison = self.analytics.compare_strategies(
                criteria,
                payload,
                thresholds=self.db.get_thresholds(),
                rules=self.db.get_rules(),
                scenario_weights=self._selected_scenario_weights(),
            )
            for item in self.compare_tree.get_children():
                self.compare_tree.delete(item)
            for row in comparison:
                self.compare_tree.insert("", "end", values=(
                    row["strategy_name"], row["winner"], f"{row['score']:.6f}"))
            self.set_status("Методи порівняно")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def run_sensitivity(self) -> None:
        try:
            criteria, payload = self.db.get_analytics_payload()
            criterion_id = self.sensitivity_criterion_var.get().split("|")[-1]
            percent = float(
                self.sensitivity_percent_var.get().replace(",", "."))
            rows = self.analytics.sensitivity_analysis(
                criteria,
                payload,
                self.strategy_var.get(),
                criterion_id,
                percent,
                thresholds=self.db.get_thresholds(),
                rules=self.db.get_rules(),
            )
            lines = ["Аналіз чутливості:"]
            for row in rows:
                delta = int(round((row["multiplier"] - 1) * 100))
                lines.append(
                    f"- Зміна ваги {delta:+d}% -> переможець: {row['winner']} (оцінка {row['score']:.6f})")
            self.analysis_text.insert("end", "\n\n" + "\n".join(lines))
            self.set_status("Чутливість обчислено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def save_scenario(self) -> None:
        selected = self.sensitivity_criterion_var.get()
        if not selected:
            messagebox.showinfo(
                "Сценарій", "Для швидкого сценарію спершу оберіть критерій для зміни ваги.")
            return
        try:
            criterion_id = selected.split("|")[-1]
            delta = float(self.sensitivity_percent_var.get().replace(",", "."))
            weights = {str(c["_id"]): float(c.get("weight", 0))
                       for c in self.criteria_cache}
            weights[criterion_id] = weights.get(criterion_id, 0) * (1 + delta)
            scenario_name = f"Сценарій {selected.split('|')[0]} {int(delta*100):+d}%"
            self.db.upsert_scenario(scenario_name, weights)
            self.refresh_scenarios()
            self.scenario_var.set(scenario_name)
            self.set_status("Сценарій збережено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def delete_scenario(self) -> None:
        if self.scenario_var.get() == "(базовий)":
            return
        self.db.delete_scenario(self.scenario_var.get())
        self.scenario_var.set("(базовий)")
        self.refresh_scenarios()
        self.set_status("Сценарій видалено")

    def seed_sample_data(self) -> None:
        try:
            self.db.seed_sample_data()
            self.refresh_all()
            self.set_status("Тестові дані завантажено")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))


if __name__ == "__main__":
    app = DSSApp()
    app.mainloop()
