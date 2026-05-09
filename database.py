from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import urlopen

from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from analytics_service import ExpertAggregationService


class Database:
    def __init__(self, uri: str = "mongodb://localhost:27017/", db_name: str = "decision_support_system_tkinter"):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[db_name]
        self.alternatives = self.db["alternatives"]
        self.criteria = self.db["criteria"]
        self.evaluations = self.db["evaluations"]
        self.thresholds = self.db["thresholds"]
        self.rules = self.db["rules"]
        self.scenarios = self.db["scenarios"]

    def ping(self) -> None:
        self.client.admin.command("ping")

    # ---------------- ALTERNATIVES ----------------
    def add_alternative(self, name: str, description: str) -> str:
        result = self.alternatives.insert_one(
            {"name": name.strip(), "description": description.strip()})
        return str(result.inserted_id)

    def get_alternatives(self) -> List[dict]:
        return list(self.alternatives.find().sort("name", 1))

    def update_alternative(self, alt_id: str, name: str, description: str) -> None:
        self.alternatives.update_one(
            {"_id": ObjectId(alt_id)},
            {"$set": {"name": name.strip(), "description": description.strip()}},
        )

    def delete_alternative(self, alt_id: str) -> None:
        alt_obj = ObjectId(alt_id)
        self.evaluations.delete_many({"alternative_id": alt_obj})
        self.alternatives.delete_one({"_id": alt_obj})

    # ---------------- CRITERIA ----------------
    def add_criterion(self, name: str, criterion_type: str, description: str, weight: float) -> str:
        result = self.criteria.insert_one(
            {
                "name": name.strip(),
                "type": criterion_type.strip(),
                "description": description.strip(),
                "weight": float(weight),
            }
        )
        return str(result.inserted_id)

    def get_criteria(self) -> List[dict]:
        return list(self.criteria.find().sort("name", 1))

    def update_criterion(self, criterion_id: str, name: str, criterion_type: str, description: str, weight: float) -> None:
        self.criteria.update_one(
            {"_id": ObjectId(criterion_id)},
            {
                "$set": {
                    "name": name.strip(),
                    "type": criterion_type.strip(),
                    "description": description.strip(),
                    "weight": float(weight),
                }
            },
        )

    def delete_criterion(self, criterion_id: str) -> None:
        criterion_obj = ObjectId(criterion_id)
        self.evaluations.delete_many({"criterion_id": criterion_obj})
        self.thresholds.delete_many({"criterion_id": str(criterion_obj)})
        self.rules.delete_many({"criterion_id": str(criterion_obj)})
        self.criteria.delete_one({"_id": criterion_obj})

    # ---------------- EVALUATIONS ----------------
    def add_evaluation(self, alternative_id: str, criterion_id: str, value: float) -> str:
        existing = self.evaluations.find_one(
            {
                "alternative_id": ObjectId(alternative_id),
                "criterion_id": ObjectId(criterion_id),
            }
        )
        if existing:
            self.evaluations.update_one({"_id": existing["_id"]}, {
                                        "$set": {"value": float(value)}})
            return "updated"
        self.evaluations.insert_one(
            {
                "alternative_id": ObjectId(alternative_id),
                "criterion_id": ObjectId(criterion_id),
                "value": float(value),
            }
        )
        return "inserted"

    def get_evaluations(self) -> List[dict]:
        return list(self.evaluations.find())

    def delete_evaluation(self, alternative_id: str, criterion_id: str) -> None:
        self.evaluations.delete_one(
            {
                "alternative_id": ObjectId(alternative_id),
                "criterion_id": ObjectId(criterion_id),
            }
        )

    # ---------------- THRESHOLDS ----------------
    def upsert_threshold(self, criterion_id: str, value: float) -> None:
        self.thresholds.update_one(
            {"criterion_id": criterion_id},
            {"$set": {"criterion_id": criterion_id, "value": float(value)}},
            upsert=True,
        )

    def delete_threshold(self, criterion_id: str) -> None:
        self.thresholds.delete_one({"criterion_id": criterion_id})

    def get_thresholds(self) -> List[dict]:
        return list(self.thresholds.find())

    # ---------------- RULES ----------------
    def add_rule(
        self,
        name: str,
        criterion_id: str,
        operator: str,
        condition_value: float,
        action: str,
        action_value: float,
    ) -> str:
        result = self.rules.insert_one(
            {
                "name": name.strip(),
                "criterion_id": criterion_id,
                "operator": operator,
                "condition_value": float(condition_value),
                "action": action,
                "action_value": float(action_value),
            }
        )
        return str(result.inserted_id)

    def get_rules(self) -> List[dict]:
        return list(self.rules.find().sort("name", 1))

    def delete_rule(self, rule_id: str) -> None:
        self.rules.delete_one({"_id": ObjectId(rule_id)})

    # ---------------- SCENARIOS ----------------
    def upsert_scenario(self, name: str, weights: Dict[str, float]) -> None:
        self.scenarios.update_one(
            {"name": name.strip()},
            {"$set": {"name": name.strip(), "weights": weights}},
            upsert=True,
        )

    def get_scenarios(self) -> List[dict]:
        return list(self.scenarios.find().sort("name", 1))

    def delete_scenario(self, name: str) -> None:
        self.scenarios.delete_one({"name": name})

    # ---------------- MATRIX / ANALYTICS ----------------
    def get_evaluation_matrix(self) -> Tuple[List[dict], List[dict]]:
        alternatives = self.get_alternatives()
        criteria = self.get_criteria()
        evaluations = list(self.evaluations.find())

        matrix = []
        for alt in alternatives:
            row = {"alternative_id": str(
                alt["_id"]), "alternative_name": alt["name"]}
            for crit in criteria:
                value = None
                for ev in evaluations:
                    if ev["alternative_id"] == alt["_id"] and ev["criterion_id"] == crit["_id"]:
                        value = ev["value"]
                        break
                row[crit["name"]] = value
            matrix.append(row)
        return criteria, matrix

    def get_analytics_payload(self) -> Tuple[List[dict], List[dict]]:
        criteria = self.get_criteria()
        alternatives = self.get_alternatives()
        evaluations = list(self.evaluations.find())
        evaluations_map: Dict[tuple, float] = {}
        for evaluation in evaluations:
            evaluations_map[(str(evaluation["alternative_id"]), str(
                evaluation["criterion_id"]))] = float(evaluation["value"])

        alternatives_payload = []
        for alternative in alternatives:
            values = {}
            for criterion in criteria:
                values[str(criterion["_id"])] = evaluations_map.get(
                    (str(alternative["_id"]), str(criterion["_id"])))
            alternatives_payload.append(
                {
                    "alternative_id": str(alternative["_id"]),
                    "alternative_name": alternative["name"],
                    "values": values,
                }
            )
        return criteria, alternatives_payload

    # ---------------- IMPORT ----------------
    def import_expert_weights_from_csv(self, source: str, method: str) -> Dict[str, float]:
        rows = self._read_csv_rows(source)
        if len(rows) < 7:
            raise ValueError("Потрібно щонайменше 7 рядків експертних оцінок.")
        criteria = self.get_criteria()
        if not criteria:
            raise ValueError("Спочатку додайте критерії в систему.")

        criteria_by_name = {
            item["name"].strip().lower(): item for item in criteria}
        aggregated: Dict[str, float] = {}
        for column_name in rows[0].keys():
            key = column_name.strip().lower()
            if key not in criteria_by_name:
                continue
            values = []
            for row in rows:
                raw = (row.get(column_name) or "").strip().replace(",", ".")
                if raw == "":
                    continue
                values.append(float(raw))
            if len(values) < 7:
                raise ValueError(
                    f"Для критерію '{column_name}' потрібно мінімум 7 оцінок.")
            aggregated[str(criteria_by_name[key]["_id"])
                       ] = ExpertAggregationService.aggregate(values, method)

        if not aggregated:
            raise ValueError(
                "У CSV не знайдено стовпців, що збігаються з назвами критеріїв.")

        total = sum(aggregated.values())
        if total <= 0:
            raise ValueError("Сума узгоджених ваг має бути більшою за 0.")

        normalized = {criterion_id: value /
                      total for criterion_id, value in aggregated.items()}
        for criterion in criteria:
            criterion_id = str(criterion["_id"])
            if criterion_id in normalized:
                self.criteria.update_one({"_id": criterion["_id"]}, {
                                         "$set": {"weight": normalized[criterion_id]}})
        return normalized

    def _normalize_google_sheets_url(self, source: str) -> str:
        parsed = urlparse(source)
        if parsed.netloc != "docs.google.com":
            return source

        path = parsed.path
        if "/spreadsheets/d/" not in path:
            return source

        parts = path.split("/")
        try:
            file_id = parts[parts.index("d") + 1]
        except (ValueError, IndexError):
            return source

        query = parsed.query
        gid = None
        for part in query.split("&"):
            if part.startswith("gid="):
                gid = part.split("=", 1)[1]
                break

        export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        if gid:
            export_url += f"&gid={gid}"
        return export_url

    def _read_csv_rows(self, source: str) -> List[Dict[str, str]]:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            source = self._normalize_google_sheets_url(source)
            with urlopen(source) as response:
                content = response.read().decode("utf-8-sig")
                return list(csv.DictReader(content.splitlines()))
        path = Path(source)
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    # ---------------- SAMPLE DATA ----------------
    def seed_sample_data(self) -> None:
        self.alternatives.delete_many({})
        self.criteria.delete_many({})
        self.evaluations.delete_many({})
        self.thresholds.delete_many({})
        self.rules.delete_many({})
        self.scenarios.delete_many({})

        alt1 = self.alternatives.insert_one(
            {"name": "Ноутбук A", "description": "Бюджетна модель для навчання"}).inserted_id
        alt2 = self.alternatives.insert_one(
            {"name": "Ноутбук B", "description": "Середній сегмент для роботи"}).inserted_id
        alt3 = self.alternatives.insert_one(
            {"name": "Ноутбук C", "description": "Потужна модель для графіки"}).inserted_id

        crit1 = self.criteria.insert_one(
            {"name": "Ціна", "type": "minimize", "description": "Вартість", "weight": 0.35}).inserted_id
        crit2 = self.criteria.insert_one(
            {"name": "Продуктивність", "type": "maximize", "description": "Швидкодія", "weight": 0.30}).inserted_id
        crit3 = self.criteria.insert_one(
            {"name": "Автономність", "type": "maximize", "description": "Час роботи", "weight": 0.20}).inserted_id
        crit4 = self.criteria.insert_one(
            {"name": "Вага", "type": "minimize", "description": "Маса пристрою", "weight": 0.15}).inserted_id

        self.evaluations.insert_many(
            [
                {"alternative_id": alt1, "criterion_id": crit1, "value": 25000},
                {"alternative_id": alt1, "criterion_id": crit2, "value": 6},
                {"alternative_id": alt1, "criterion_id": crit3, "value": 8},
                {"alternative_id": alt1, "criterion_id": crit4, "value": 1.8},
                {"alternative_id": alt2, "criterion_id": crit1, "value": 32000},
                {"alternative_id": alt2, "criterion_id": crit2, "value": 8},
                {"alternative_id": alt2, "criterion_id": crit3, "value": 7},
                {"alternative_id": alt2, "criterion_id": crit4, "value": 1.5},
                {"alternative_id": alt3, "criterion_id": crit1, "value": 45000},
                {"alternative_id": alt3, "criterion_id": crit2, "value": 10},
                {"alternative_id": alt3, "criterion_id": crit3, "value": 6},
                {"alternative_id": alt3, "criterion_id": crit4, "value": 2.1},
            ]
        )

        self.upsert_threshold(str(crit3), 6.0)
        self.add_rule(
            name="Премія за високу продуктивність",
            criterion_id=str(crit2),
            operator=">=",
            condition_value=9,
            action="bonus",
            action_value=0.05,
        )

    # ---------------- HELPERS ----------------
    def safe_call(self, func, *args, **kwargs):
        try:
            self.ping()
            return func(*args, **kwargs)
        except PyMongoError as exc:
            raise ConnectionError(
                "Не вдалося підключитися до MongoDB. Перевірте, чи запущено службу MongoDB / MongoDB Compass і чи правильний URI."
            ) from exc
