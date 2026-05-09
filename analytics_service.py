from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from statistics import median
from typing import Dict, Iterable, List, Optional


@dataclass
class CriterionInfo:
    criterion_id: str
    name: str
    criterion_type: str
    weight: float


@dataclass
class RuleResult:
    rule_name: str
    action: str
    value: float
    reason: str


class EvaluationStrategy(ABC):
    name: str
    description: str

    @abstractmethod
    def calculate(self, normalized_values: List[float], weights: List[float]) -> float:
        raise NotImplementedError


class AdditiveStrategy(EvaluationStrategy):
    name = "Адитивна згортка"
    description = "Q(Ai) = Σ(Wj * Xij)"

    def calculate(self, normalized_values: List[float], weights: List[float]) -> float:
        return sum(weight * value for weight, value in zip(weights, normalized_values))


class MultiplicativeStrategy(EvaluationStrategy):
    name = "Мультиплікативна згортка"
    description = "Q(Ai) = Π(Xij ^ Wj)"

    def calculate(self, normalized_values: List[float], weights: List[float]) -> float:
        result = 1.0
        for value, weight in zip(normalized_values, weights):
            safe_value = max(value, 1e-12)
            result *= safe_value ** weight
        return result


class CautiousStrategy(EvaluationStrategy):
    name = "Обережна стратегія"
    description = "Q(Ai) = min(Wj * Xij)"

    def calculate(self, normalized_values: List[float], weights: List[float]) -> float:
        return min(weight * value for weight, value in zip(weights, normalized_values))


class ExpertAggregationService:
    METHODS = {
        "mean": "Середнє арифметичне",
        "median": "Медіана",
        "trimmed_mean": "Усічене середнє (без min/max)",
    }

    @classmethod
    def aggregate(cls, values: Iterable[float], method: str) -> float:
        data = [float(v) for v in values]
        if not data:
            raise ValueError("Немає значень для агрегування.")
        if method == "mean":
            return sum(data) / len(data)
        if method == "median":
            return float(median(data))
        if method == "trimmed_mean":
            ordered = sorted(data)
            if len(ordered) > 2:
                ordered = ordered[1:-1]
            return sum(ordered) / len(ordered)
        raise ValueError("Невідомий метод узгодження експертних оцінок.")


class AnalyticsService:
    def __init__(self) -> None:
        self._strategies = {
            "1": AdditiveStrategy(),
            "2": MultiplicativeStrategy(),
            "3": CautiousStrategy(),
        }

    def get_strategy_menu(self) -> Dict[str, EvaluationStrategy]:
        return self._strategies

    def evaluate(
        self,
        criteria: List[dict],
        alternatives_payload: List[dict],
        strategy_key: str,
        thresholds: Optional[List[dict]] = None,
        rules: Optional[List[dict]] = None,
        scenario_weights: Optional[Dict[str, float]] = None,
    ) -> dict:
        strategy = self._strategies.get(strategy_key)
        if strategy is None:
            raise ValueError("Невідома стратегія оцінювання.")

        if not criteria:
            raise ValueError("У системі немає критеріїв.")
        if not alternatives_payload:
            raise ValueError("У системі немає альтернатив з оцінками.")

        prepared_criteria = self._prepare_criteria(criteria, scenario_weights)
        self._validate_weights(prepared_criteria)
        normalized_weights = self._normalize_weights([c.weight for c in prepared_criteria])

        criterion_meta = []
        for index, criterion in enumerate(prepared_criteria):
            criterion_meta.append(
                {
                    "criterion_id": criterion.criterion_id,
                    "name": criterion.name,
                    "type": criterion.criterion_type,
                    "weight": criterion.weight,
                    "normalized_weight": normalized_weights[index],
                }
            )

        filtered_alternatives, threshold_log = self._apply_thresholds(
            prepared_criteria,
            alternatives_payload,
            thresholds or [],
        )
        if not filtered_alternatives:
            raise ValueError("Після порогової обробки не залишилося допустимих альтернатив.")

        normalized_matrix = self._normalize_matrix(prepared_criteria, filtered_alternatives)

        results = []
        rules_log: Dict[str, List[RuleResult]] = {}
        for alternative in filtered_alternatives:
            normalized_values = [
                normalized_matrix[alternative["alternative_id"]][criterion.criterion_id]
                for criterion in prepared_criteria
            ]

            base_score = strategy.calculate(normalized_values, normalized_weights)
            details = []
            for index, criterion in enumerate(prepared_criteria):
                contribution = normalized_values[index] * normalized_weights[index]
                details.append(
                    {
                        "criterion_name": criterion.name,
                        "raw_value": alternative["values"][criterion.criterion_id],
                        "normalized_value": normalized_values[index],
                        "weight": normalized_weights[index],
                        "criterion_type": criterion.criterion_type,
                        "contribution": contribution,
                    }
                )

            adjusted_score, applied_rules = self._apply_rules(
                alternative=alternative,
                criteria=prepared_criteria,
                base_score=base_score,
                rules=rules or [],
            )
            rules_log[alternative["alternative_id"]] = applied_rules

            results.append(
                {
                    "alternative_id": alternative["alternative_id"],
                    "alternative_name": alternative["alternative_name"],
                    "score": adjusted_score,
                    "base_score": base_score,
                    "details": details,
                    "applied_rules": [r.__dict__ for r in applied_rules],
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        best = results[0]
        explanation = self._build_explanation(best, threshold_log)

        return {
            "strategy_name": strategy.name,
            "strategy_formula": strategy.description,
            "criteria": criterion_meta,
            "results": results,
            "best": best,
            "explanation": explanation,
            "threshold_log": threshold_log,
        }

    def compare_strategies(
        self,
        criteria: List[dict],
        alternatives_payload: List[dict],
        thresholds: Optional[List[dict]] = None,
        rules: Optional[List[dict]] = None,
        scenario_weights: Optional[Dict[str, float]] = None,
    ) -> List[dict]:
        comparison = []
        for key, strategy in self._strategies.items():
            result = self.evaluate(
                criteria,
                alternatives_payload,
                key,
                thresholds=thresholds,
                rules=rules,
                scenario_weights=scenario_weights,
            )
            comparison.append(
                {
                    "strategy_key": key,
                    "strategy_name": strategy.name,
                    "winner": result["best"]["alternative_name"],
                    "score": result["best"]["score"],
                }
            )
        return comparison

    def sensitivity_analysis(
        self,
        criteria: List[dict],
        alternatives_payload: List[dict],
        strategy_key: str,
        criterion_id: str,
        change_percent: float,
        thresholds: Optional[List[dict]] = None,
        rules: Optional[List[dict]] = None,
    ) -> List[dict]:
        base_map = {str(item["_id"]): float(item.get("weight", 0)) for item in criteria}
        if criterion_id not in base_map:
            raise ValueError("Критерій для аналізу чутливості не знайдено.")

        multipliers = [1 - change_percent, 1.0, 1 + change_percent]
        rows = []
        for multiplier in multipliers:
            scenario_weights = dict(base_map)
            scenario_weights[criterion_id] = max(0.0, base_map[criterion_id] * multiplier)
            result = self.evaluate(
                criteria,
                alternatives_payload,
                strategy_key,
                thresholds=thresholds,
                rules=rules,
                scenario_weights=scenario_weights,
            )
            rows.append(
                {
                    "multiplier": multiplier,
                    "winner": result["best"]["alternative_name"],
                    "score": result["best"]["score"],
                }
            )
        return rows

    def _prepare_criteria(
        self,
        criteria: List[dict],
        scenario_weights: Optional[Dict[str, float]] = None,
    ) -> List[CriterionInfo]:
        prepared = []
        for criterion in criteria:
            criterion_id = str(criterion["_id"])
            weight = float(criterion.get("weight", 0))
            if scenario_weights and criterion_id in scenario_weights:
                weight = float(scenario_weights[criterion_id])
            prepared.append(
                CriterionInfo(
                    criterion_id=criterion_id,
                    name=criterion["name"],
                    criterion_type=criterion["type"],
                    weight=weight,
                )
            )
        return prepared

    def _validate_weights(self, criteria: List[CriterionInfo]) -> None:
        for criterion in criteria:
            if criterion.weight < 0:
                raise ValueError(f"Вага критерію '{criterion.name}' не може бути від'ємною.")
        if all(criterion.weight == 0 for criterion in criteria):
            raise ValueError("Усі ваги дорівнюють 0. Задайте хоча б одну ненульову вагу.")

    def _normalize_weights(self, weights: List[float]) -> List[float]:
        total = sum(weights)
        if total == 0:
            raise ValueError("Сума ваг дорівнює 0.")
        return [weight / total for weight in weights]

    def _apply_thresholds(
        self,
        criteria: List[CriterionInfo],
        alternatives_payload: List[dict],
        thresholds: List[dict],
    ) -> tuple[List[dict], List[str]]:
        if not thresholds:
            return alternatives_payload, []

        criteria_map = {c.criterion_id: c for c in criteria}
        allowed = []
        messages: List[str] = []
        for alternative in alternatives_payload:
            rejected = False
            for threshold in thresholds:
                criterion_id = threshold.get("criterion_id")
                value = alternative["values"].get(criterion_id)
                if value is None or criterion_id not in criteria_map:
                    continue
                criterion = criteria_map[criterion_id]
                limit = float(threshold.get("value", 0))
                if criterion.criterion_type == "maximize" and float(value) < limit:
                    rejected = True
                    messages.append(
                        f"Альтернатива '{alternative['alternative_name']}' відсіяна: {criterion.name} = {value} < {limit}."
                    )
                    break
                if criterion.criterion_type == "minimize" and float(value) > limit:
                    rejected = True
                    messages.append(
                        f"Альтернатива '{alternative['alternative_name']}' відсіяна: {criterion.name} = {value} > {limit}."
                    )
                    break
            if not rejected:
                allowed.append(alternative)
        return allowed, messages

    def _apply_rules(
        self,
        alternative: dict,
        criteria: List[CriterionInfo],
        base_score: float,
        rules: List[dict],
    ) -> tuple[float, List[RuleResult]]:
        criteria_map = {c.criterion_id: c for c in criteria}
        score = base_score
        applied: List[RuleResult] = []

        for rule in rules:
            criterion_id = rule.get("criterion_id")
            if criterion_id not in criteria_map:
                continue
            raw_value = alternative["values"].get(criterion_id)
            if raw_value is None:
                continue
            operator = rule.get("operator", ">=")
            condition_value = float(rule.get("condition_value", 0))
            if not self._check_condition(float(raw_value), operator, condition_value):
                continue

            action = rule.get("action", "bonus")
            action_value = float(rule.get("action_value", 0))
            rule_name = rule.get("name", "Без назви")
            if action == "exclude":
                score = -1.0
                applied.append(
                    RuleResult(
                        rule_name=rule_name,
                        action=action,
                        value=action_value,
                        reason=f"Альтернатива виключена правилом '{rule_name}'.",
                    )
                )
                break
            if action == "bonus":
                score += action_value
                applied.append(
                    RuleResult(
                        rule_name=rule_name,
                        action=action,
                        value=action_value,
                        reason=f"Застосовано бонус +{action_value:.3f} за правилом '{rule_name}'.",
                    )
                )
            elif action == "penalty":
                score -= action_value
                applied.append(
                    RuleResult(
                        rule_name=rule_name,
                        action=action,
                        value=action_value,
                        reason=f"Застосовано штраф -{action_value:.3f} за правилом '{rule_name}'.",
                    )
                )
        return score, applied

    def _check_condition(self, left: float, operator: str, right: float) -> bool:
        if operator == ">=":
            return left >= right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == "<":
            return left < right
        if operator == "==":
            return abs(left - right) < 1e-9
        raise ValueError("Непідтримуваний оператор правила.")

    def _normalize_matrix(
        self,
        criteria: List[CriterionInfo],
        alternatives_payload: List[dict],
    ) -> Dict[str, Dict[str, float]]:
        normalized: Dict[str, Dict[str, float]] = {}
        for alternative in alternatives_payload:
            normalized[alternative["alternative_id"]] = {}

        for criterion in criteria:
            values: List[float] = []
            for alternative in alternatives_payload:
                raw_value = alternative["values"].get(criterion.criterion_id)
                if raw_value is None:
                    raise ValueError(
                        f"Для альтернативи '{alternative['alternative_name']}' відсутня оцінка за критерієм '{criterion.name}'."
                    )
                values.append(float(raw_value))

            if criterion.criterion_type == "maximize":
                divisor = max(values)
                normalized_values = [0.0 if divisor == 0 else value / divisor for value in values]
            elif criterion.criterion_type == "minimize":
                positive_values = [value for value in values if value > 0]
                if not positive_values:
                    raise ValueError(
                        f"Для критерію '{criterion.name}' з типом minimize усі значення мають бути > 0."
                    )
                minimum_value = min(positive_values)
                normalized_values = [minimum_value / value if value > 0 else 0.0 for value in values]
            else:
                raise ValueError(
                    f"Критерій '{criterion.name}' має некоректний тип. Допустимо: maximize або minimize."
                )

            for index, alternative in enumerate(alternatives_payload):
                normalized[alternative["alternative_id"]][criterion.criterion_id] = normalized_values[index]

        return normalized

    def _build_explanation(self, best: dict, threshold_log: List[str]) -> str:
        strongest_detail = max(best["details"], key=lambda item: item["contribution"])
        weakest_detail = min(best["details"], key=lambda item: item["contribution"])
        parts = [
            f"Переможець '{best['alternative_name']}' отримав найбільшу інтегральну оцінку.",
            f"Найбільший внесок дав критерій '{strongest_detail['criterion_name']}',",
            f"найменший — '{weakest_detail['criterion_name']}'.",
        ]
        if best.get("applied_rules"):
            parts.append("До фінальної оцінки також були застосовані експертні правила.")
        if threshold_log:
            parts.append("Перед ранжуванням частина альтернатив була відсіяна пороговою обробкою.")
        return " ".join(parts)
