import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("railway_eta.services.explanation")


class FactorContribution(BaseModel):
    category: str  # "SPEED", "DELAY", "CONGESTION", "WEATHER", "STATION_HALT", "RECOVERY", "SECTIONAL_RUNTIME"
    direction: str # "INCREASED_ETA", "DECREASED_ETA", "NEUTRAL"
    impact_description: str
    metric_evidence: str


class ETAChangeExplanation(BaseModel):
    train_number: str
    station_code: str
    station_name: str
    previous_eta: Optional[str] = None
    new_eta: str
    shift_minutes: float
    direction: str  # "DELAY_INCREASED", "DELAY_REDUCED", "UNCHANGED"
    summary: str
    contributing_factors: List[FactorContribution] = Field(default_factory=list)
    generated_at: str


class ExplanationEngine:
    """
    Deterministic Explanation Engine for Railway ETA Discrepancies.
    
    Principles:
    1. NEVER use an LLM for core prediction or causal attribution.
    2. Inspect genuine telemetry metrics:
       - Speed differential (delta v)
       - Instantaneous delay drift (delta d)
       - Corridor congestion transition
       - Environmental weather factors
       - Halt / signal check status
       - Recovery / timetable slack
    3. Strictly output operational factors verified by actual telemetry deltas.
    4. Never fabricate reasons.
    """

    @classmethod
    def explain_eta_change(
        cls,
        train_number: str,
        station_code: str,
        station_name: str,
        previous_eta_iso: Optional[str],
        new_eta_iso: str,
        shift_minutes: float,
        # Telemetry & Operational State:
        current_speed: float,
        previous_speed: Optional[float],
        current_delay: float,
        previous_delay: Optional[float],
        operational_event: str,
        congestion_level: str,
        weather_info: Optional[Dict[str, Any]] = None,
        is_halted: bool = False
    ) -> ETAChangeExplanation:
        from datetime import datetime, timezone
        factors: List[FactorContribution] = []

        # 1. Inspect Speed Changes
        if previous_speed is not None:
            speed_delta = current_speed - previous_speed
            if speed_delta <= -15.0:
                factors.append(FactorContribution(
                    category="SPEED",
                    direction="INCREASED_ETA",
                    impact_description="Train speed dropped significantly below permissible sectional velocity",
                    metric_evidence=f"Speed decreased from {round(previous_speed, 1)} km/h to {round(current_speed, 1)} km/h"
                ))
            elif speed_delta >= 15.0:
                factors.append(FactorContribution(
                    category="SPEED",
                    direction="DECREASED_ETA",
                    impact_description="Train accelerated towards permissible line speed",
                    metric_evidence=f"Speed increased from {round(previous_speed, 1)} km/h to {round(current_speed, 1)} km/h"
                ))
        elif current_speed < 45.0 and operational_event != "UNSCHEDULED_HALT":
            factors.append(FactorContribution(
                category="SPEED",
                direction="INCREASED_ETA",
                impact_description="Locomotive operating under cautionary restricted speed",
                metric_evidence=f"Current speed {round(current_speed, 1)} km/h (< 45 km/h threshold)"
            ))

        # 2. Inspect Accumulated Delay Drift
        if previous_delay is not None:
            delay_delta = current_delay - previous_delay
            if delay_delta >= 1.0:
                factors.append(FactorContribution(
                    category="DELAY",
                    direction="INCREASED_ETA",
                    impact_description="Cumulative operational delay accumulated along block section",
                    metric_evidence=f"Delay increased by +{round(delay_delta, 1)} min (now +{round(current_delay, 1)} min)"
                ))
            elif delay_delta <= -1.0:
                factors.append(FactorContribution(
                    category="DELAY",
                    direction="DECREASED_ETA",
                    impact_description="Locomotive made up lost time across section",
                    metric_evidence=f"Delay reduced by {round(abs(delay_delta), 1)} min (now +{round(current_delay, 1)} min)"
                ))

        # 3. Inspect Operational Disruption / Congestion
        if operational_event == "CONGESTION" or congestion_level == "HIGH":
            factors.append(FactorContribution(
                category="CONGESTION",
                direction="INCREASED_ETA",
                impact_description="Severe track block congestion and signal queuing detected on upcoming section",
                metric_evidence=f"Congestion status: {congestion_level}, Event: {operational_event}"
            ))
        elif operational_event == "SPEED_RESTRICTION" or congestion_level == "MEDIUM":
            factors.append(FactorContribution(
                category="CONGESTION",
                direction="INCREASED_ETA",
                impact_description="Speed restriction / cautionary order active on track block",
                metric_evidence=f"Active restriction: {operational_event}"
            ))

        # 4. Inspect Station Halt / Stalled Train
        if is_halted or operational_event == "UNSCHEDULED_HALT" or current_speed < 1.0:
            factors.append(FactorContribution(
                category="STATION_HALT",
                direction="INCREASED_ETA",
                impact_description="Locomotive halted outside station at red signal aspect",
                metric_evidence=f"Speed: {round(current_speed, 1)} km/h, Event: {operational_event}"
            ))

        # 5. Inspect Recovery / Priority Routing
        if operational_event == "RECOVERY":
            factors.append(FactorContribution(
                category="RECOVERY",
                direction="DECREASED_ETA",
                impact_description="Priority green signal aspect assigned; utilizing engineered timetable recovery slack",
                metric_evidence="Operational mode: RECOVERY (Speed: ~130 km/h)"
            ))

        # 6. Inspect Environmental Weather
        if weather_info:
            is_severe = weather_info.get("is_severe_weather", False)
            precip = weather_info.get("precipitation_mm", 0.0)
            vis = weather_info.get("visibility_km", 10.0)
            cond = weather_info.get("weather_condition", "Clear")

            if is_severe or vis < 2.0 or precip > 15.0:
                factors.append(FactorContribution(
                    category="WEATHER",
                    direction="INCREASED_ETA",
                    impact_description=f"Adverse environmental weather condition ({cond}) enforcing safety headway",
                    metric_evidence=f"Visibility: {vis} km, Rain: {precip} mm"
                ))

        # Direction and Summary formulation
        if shift_minutes > 0.5:
            direction = "DELAY_INCREASED"
            summary = f"ETA deferred by approximately {abs(round(shift_minutes, 1))} minutes due to operational factors."
        elif shift_minutes < -0.5:
            direction = "DELAY_REDUCED"
            summary = f"ETA advanced by approximately {abs(round(shift_minutes, 1))} minutes due to timetable slack recovery."
        else:
            direction = "UNCHANGED"
            summary = "ETA consistent with scheduled sectional running parameters."

        return ETAChangeExplanation(
            train_number=train_number,
            station_code=station_code,
            station_name=station_name,
            previous_eta=previous_eta_iso,
            new_eta=new_eta_iso,
            shift_minutes=round(shift_minutes, 1),
            direction=direction,
            summary=summary,
            contributing_factors=factors,
            generated_at=datetime.now(timezone.utc).isoformat()
        )


explanation_service = ExplanationEngine()
