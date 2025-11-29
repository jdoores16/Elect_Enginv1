"""
Circuit Aggregation Service

Combines data from multiple photo uploads to:
1. Increase confidence when multiple sources agree
2. Merge complementary information from different sources
3. Detect and flag conflicts when sources disagree
4. Track provenance (which photo each value came from)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math

logger = logging.getLogger(__name__)


class ExtractionMethod(Enum):
    TEXT_OCR = "text_ocr"
    AI_VISION = "ai_vision"
    MANUAL = "manual"
    AI_OCR_FALLBACK = "ai_ocr_fallback"


# Base confidence weights per extraction method
METHOD_CONFIDENCE_WEIGHTS = {
    ExtractionMethod.MANUAL: 0.70,       # Voice/text input from user
    ExtractionMethod.AI_VISION: 0.85,    # Visual nameplate detection
    ExtractionMethod.AI_OCR_FALLBACK: 0.70,
    ExtractionMethod.TEXT_OCR: 0.60,     # Basic text OCR
}


@dataclass
class FieldObservation:
    """A single observation of a field value from a source"""
    value: Any
    confidence: float
    source_id: str  # filename or upload ID
    method: ExtractionMethod
    timestamp: datetime = field(default_factory=datetime.now)
    
    def effective_confidence(self) -> float:
        """Calculate effective confidence considering method weight"""
        base_weight = METHOD_CONFIDENCE_WEIGHTS.get(self.method, 0.5)
        return min(1.0, self.confidence * base_weight)


@dataclass
class CircuitObservation:
    """Observation of a circuit from a single source"""
    circuit_num: int
    source_id: str
    method: ExtractionMethod
    timestamp: datetime
    description: Optional[str] = None
    description_confidence: float = 0.0
    breaker_amps: Optional[int] = None
    amps_confidence: float = 0.0
    poles: Optional[int] = None
    poles_confidence: float = 0.0
    load_amps: Optional[float] = None
    load_confidence: float = 0.0
    load_type: Optional[str] = None  # LTG, RCP, MTR, C, NC
    load_type_confidence: float = 0.0


@dataclass
class ResolvedField:
    """Resolved value for a field with confidence and provenance"""
    value: Any
    confidence: float
    sources: List[str]  # List of source_ids that contributed
    has_conflict: bool = False
    competing_values: List[Tuple[Any, float]] = field(default_factory=list)


@dataclass
class ResolvedCircuit:
    """Resolved circuit data combining multiple observations"""
    circuit_num: int
    description: ResolvedField
    breaker_amps: ResolvedField
    poles: ResolvedField
    load_amps: ResolvedField
    load_type: ResolvedField = field(default_factory=lambda: ResolvedField(None, 0.0, []))
    observations_count: int = 0
    needs_review: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            'number': str(self.circuit_num),
            'description': self.description.value or '',
            'breaker_amps': self.breaker_amps.value or 0,
            'poles': self.poles.value or 1,
            'load_amps': self.load_amps.value or 0,
            'load_type': self.load_type.value or '',
            'confidence': {
                'description': round(self.description.confidence, 2),
                'breaker_amps': round(self.breaker_amps.confidence, 2),
                'poles': round(self.poles.confidence, 2),
                'load_type': round(self.load_type.confidence, 2),
                'overall': round(self._overall_confidence(), 2)
            },
            'sources': list(set(
                self.description.sources + 
                self.breaker_amps.sources + 
                self.poles.sources +
                self.load_type.sources
            )),
            'has_conflicts': any([
                self.description.has_conflict,
                self.breaker_amps.has_conflict,
                self.poles.has_conflict,
                self.load_type.has_conflict
            ]),
            'needs_review': self.needs_review,
            'observations_count': self.observations_count
        }
    
    def _overall_confidence(self) -> float:
        """Calculate overall circuit confidence"""
        confidences = []
        if self.description.value:
            confidences.append(self.description.confidence)
        if self.breaker_amps.value:
            confidences.append(self.breaker_amps.confidence)
        if self.poles.value:
            confidences.append(self.poles.confidence)
        if self.load_type.value:
            confidences.append(self.load_type.confidence)
        return sum(confidences) / len(confidences) if confidences else 0.0


class CircuitAggregationService:
    """
    Service for aggregating circuit data from multiple sources.
    
    Features:
    - Stores all observations with provenance
    - Combines matching values using probabilistic fusion
    - Merges complementary data from different sources
    - Detects and flags conflicts
    """
    
    CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence to consider resolved
    CONFLICT_THRESHOLD = 0.3   # Minimum confidence to consider a competing value
    
    def __init__(self):
        # Per-task storage: task_id -> circuit_num -> list of observations
        self._observations: Dict[str, Dict[int, List[CircuitObservation]]] = {}
        # Cached resolved circuits per task
        self._resolved_cache: Dict[str, Dict[int, ResolvedCircuit]] = {}
    
    def add_observation(
        self,
        task_id: str,
        circuit_num: int,
        source_id: str,
        method: ExtractionMethod,
        description: Optional[str] = None,
        description_confidence: float = 0.8,
        breaker_amps: Optional[int] = None,
        amps_confidence: float = 0.8,
        poles: Optional[int] = None,
        poles_confidence: float = 0.8,
        load_amps: Optional[float] = None,
        load_confidence: float = 0.8,
        load_type: Optional[str] = None,
        load_type_confidence: float = 0.8
    ) -> None:
        """Add a new observation from a source"""
        if task_id not in self._observations:
            self._observations[task_id] = {}
        
        if circuit_num not in self._observations[task_id]:
            self._observations[task_id][circuit_num] = []
        
        observation = CircuitObservation(
            circuit_num=circuit_num,
            source_id=source_id,
            method=method,
            timestamp=datetime.now(),
            description=description,
            description_confidence=description_confidence,
            breaker_amps=breaker_amps,
            amps_confidence=amps_confidence,
            poles=poles,
            poles_confidence=poles_confidence,
            load_amps=load_amps,
            load_confidence=load_confidence,
            load_type=load_type,
            load_type_confidence=load_type_confidence
        )
        
        self._observations[task_id][circuit_num].append(observation)
        
        # Invalidate cache for this task
        if task_id in self._resolved_cache:
            if circuit_num in self._resolved_cache[task_id]:
                del self._resolved_cache[task_id][circuit_num]
        
        logger.info(f"Added observation for circuit {circuit_num} from {source_id} ({method.value})")
    
    def add_observations_from_ocr_result(
        self,
        task_id: str,
        source_id: str,
        circuits: List[Dict],
        method: ExtractionMethod = ExtractionMethod.TEXT_OCR,
        visual_breakers: Optional[Dict] = None
    ) -> List[str]:
        """
        Add observations from OCR/vision processing results.
        
        Returns list of "BREAKER INFO FOUND" notifications for new data.
        """
        notifications = []
        
        for circuit in circuits:
            circuit_num = int(circuit.get('number', 0))
            if circuit_num <= 0:
                continue
            
            desc = circuit.get('description')
            if desc == 'MISSING':
                desc = None
            
            amps = circuit.get('breaker_amps')
            if amps == 'MISSING':
                amps = None
            elif amps is not None:
                try:
                    amps = int(amps)
                except (ValueError, TypeError):
                    amps = None
            
            poles = circuit.get('breaker_poles')
            if poles == 'MISSING':
                poles = None
            elif poles is not None:
                try:
                    poles = int(poles)
                except (ValueError, TypeError):
                    poles = None
            
            load_type = circuit.get('load_type')
            if load_type == 'MISSING':
                load_type = None
            elif load_type is not None:
                load_type = str(load_type).upper().strip()
                if load_type not in ['LTG', 'RCP', 'MTR', 'C', 'NC']:
                    load_type = None
            
            # Check for visual pole detection override
            detection_method = method
            if circuit.get('visual_pole_detection'):
                detection_method = ExtractionMethod.AI_VISION
            
            # Skip if no actual data
            if desc is None and amps is None and poles is None and load_type is None:
                continue
            
            # Get existing resolved data before adding
            existing = self.get_resolved_circuit(task_id, circuit_num)
            
            # Add the observation
            self.add_observation(
                task_id=task_id,
                circuit_num=circuit_num,
                source_id=source_id,
                method=detection_method,
                description=desc,
                description_confidence=circuit.get('confidence', 0.8),
                breaker_amps=amps,
                amps_confidence=0.8,
                poles=poles,
                poles_confidence=0.9 if circuit.get('visual_pole_detection') else 0.7,
                load_type=load_type,
                load_type_confidence=0.8
            )
            
            # Get new resolved data after adding
            new_resolved = self.get_resolved_circuit(task_id, circuit_num)
            
            # Build notification ONLY if data actually changed
            if new_resolved is not None:
                changed_parts = []
                is_new_circuit = existing is None
                
                # Check each field for changes
                existing_poles = existing.poles.value if existing else None
                existing_amps = existing.breaker_amps.value if existing else None
                existing_desc = existing.description.value if existing else None
                existing_load_type = existing.load_type.value if existing else None
                
                if new_resolved.poles.value and new_resolved.poles.value != existing_poles:
                    changed_parts.append(f"{new_resolved.poles.value}-pole")
                
                if new_resolved.breaker_amps.value and new_resolved.breaker_amps.value != existing_amps:
                    changed_parts.append(f"{new_resolved.breaker_amps.value}A")
                
                if new_resolved.description.value and new_resolved.description.value != existing_desc:
                    changed_parts.append(f"'{new_resolved.description.value}'")
                
                if new_resolved.load_type.value and new_resolved.load_type.value != existing_load_type:
                    changed_parts.append(f"type:{new_resolved.load_type.value}")
                
                # Only notify if something actually changed
                if changed_parts:
                    if is_new_circuit:
                        notification = f"BREAKER INFO FOUND - Circuit {circuit_num}: {', '.join(changed_parts)}"
                    else:
                        notification = f"BREAKER INFO UPDATED - Circuit {circuit_num}: {', '.join(changed_parts)}"
                    
                    if new_resolved.observations_count > 1:
                        notification += f" (combined from {new_resolved.observations_count} sources)"
                    elif detection_method == ExtractionMethod.AI_VISION:
                        notification += " (AI Vision)"
                    
                    notifications.append(notification)
                    logger.info(notification)
        
        # Also process AI Vision breakers if provided
        if visual_breakers and visual_breakers.get('ai_vision_success'):
            for breaker in visual_breakers.get('breakers', []):
                circuits_list = breaker.get('circuits', [])
                poles = breaker.get('poles')
                amps = breaker.get('amps')
                desc = breaker.get('description')
                breaker_load_type = breaker.get('load_type')
                if breaker_load_type:
                    breaker_load_type = str(breaker_load_type).upper().strip()
                    if breaker_load_type not in ['LTG', 'RCP', 'MTR', 'C', 'NC']:
                        breaker_load_type = None
                
                if not circuits_list:
                    continue
                
                for circuit_num in circuits_list:
                    self.add_observation(
                        task_id=task_id,
                        circuit_num=circuit_num,
                        source_id=source_id,
                        method=ExtractionMethod.AI_VISION,
                        description=desc if desc else None,
                        description_confidence=0.85,
                        breaker_amps=amps,
                        amps_confidence=0.85,
                        poles=poles,
                        poles_confidence=0.90,
                        load_type=breaker_load_type,
                        load_type_confidence=0.85
                    )
        
        return notifications
    
    def get_resolved_circuit(self, task_id: str, circuit_num: int) -> Optional[ResolvedCircuit]:
        """Get resolved circuit data combining all observations"""
        if task_id not in self._observations:
            return None
        
        if circuit_num not in self._observations[task_id]:
            return None
        
        # Check cache
        if task_id in self._resolved_cache:
            if circuit_num in self._resolved_cache[task_id]:
                return self._resolved_cache[task_id][circuit_num]
        
        observations = self._observations[task_id][circuit_num]
        
        # Resolve each field
        description = self._resolve_field(
            [(obs.description, obs.description_confidence, obs.source_id, obs.method) 
             for obs in observations if obs.description]
        )
        
        breaker_amps = self._resolve_field(
            [(obs.breaker_amps, obs.amps_confidence, obs.source_id, obs.method) 
             for obs in observations if obs.breaker_amps is not None]
        )
        
        poles = self._resolve_field(
            [(obs.poles, obs.poles_confidence, obs.source_id, obs.method) 
             for obs in observations if obs.poles is not None]
        )
        
        load_amps = self._resolve_field(
            [(obs.load_amps, obs.load_confidence, obs.source_id, obs.method) 
             for obs in observations if obs.load_amps is not None]
        )
        
        load_type = self._resolve_field(
            [(obs.load_type, obs.load_type_confidence, obs.source_id, obs.method) 
             for obs in observations if obs.load_type]
        )
        
        resolved = ResolvedCircuit(
            circuit_num=circuit_num,
            description=description,
            breaker_amps=breaker_amps,
            poles=poles,
            load_amps=load_amps,
            load_type=load_type,
            observations_count=len(observations),
            needs_review=any([
                description.has_conflict,
                breaker_amps.has_conflict,
                poles.has_conflict,
                load_type.has_conflict
            ])
        )
        
        # Cache result
        if task_id not in self._resolved_cache:
            self._resolved_cache[task_id] = {}
        self._resolved_cache[task_id][circuit_num] = resolved
        
        return resolved
    
    def get_all_resolved_circuits(self, task_id: str) -> Dict[int, ResolvedCircuit]:
        """Get all resolved circuits for a task"""
        if task_id not in self._observations:
            return {}
        
        result = {}
        for circuit_num in self._observations[task_id]:
            resolved = self.get_resolved_circuit(task_id, circuit_num)
            if resolved:
                result[circuit_num] = resolved
        
        return result
    
    def get_aggregation_summary(self, task_id: str) -> Dict:
        """Get summary of aggregation state for a task"""
        if task_id not in self._observations:
            return {
                'total_circuits': 0,
                'total_observations': 0,
                'circuits_with_conflicts': 0,
                'average_confidence': 0.0,
                'sources': []
            }
        
        all_resolved = self.get_all_resolved_circuits(task_id)
        all_sources = set()
        total_confidence = 0.0
        conflicts = 0
        
        for circuit in all_resolved.values():
            all_sources.update(circuit.description.sources)
            all_sources.update(circuit.breaker_amps.sources)
            all_sources.update(circuit.poles.sources)
            total_confidence += circuit._overall_confidence()
            if circuit.needs_review:
                conflicts += 1
        
        return {
            'total_circuits': len(all_resolved),
            'total_observations': sum(
                len(obs) for obs in self._observations[task_id].values()
            ),
            'circuits_with_conflicts': conflicts,
            'average_confidence': round(
                total_confidence / len(all_resolved) if all_resolved else 0.0, 2
            ),
            'sources': list(all_sources)
        }
    
    def _resolve_field(
        self, 
        observations: List[Tuple[Any, float, str, ExtractionMethod]]
    ) -> ResolvedField:
        """
        Resolve a field from multiple observations.
        
        Uses probabilistic fusion: combined_conf = 1 - ∏(1 - conf_i)
        Weight is applied as a ceiling, not multiplier, to avoid double-counting.
        """
        if not observations:
            return ResolvedField(value=None, confidence=0.0, sources=[])
        
        # Group by value (normalize strings for comparison)
        value_groups: Dict[Any, List[Tuple[float, str, ExtractionMethod]]] = {}
        for value, conf, source, method in observations:
            # Normalize string values for comparison
            normalized_value = value.strip().lower() if isinstance(value, str) else value
            if normalized_value not in value_groups:
                value_groups[normalized_value] = []
            value_groups[normalized_value].append((conf, source, method, value))
        
        # Calculate combined confidence for each unique value
        value_confidences: List[Tuple[Any, float, List[str]]] = []
        
        for normalized_value, obs_list in value_groups.items():
            # Use the original (non-normalized) value from first observation
            original_value = obs_list[0][3]
            
            # Probabilistic fusion: 1 - ∏(1 - conf_i)
            # Weight limits max confidence per method, doesn't multiply
            product = 1.0
            sources = []
            for conf, source, method, _ in obs_list:
                weight = METHOD_CONFIDENCE_WEIGHTS.get(method, 0.5)
                # Cap confidence at method weight, don't multiply
                effective_conf = min(conf, weight)
                product *= (1.0 - effective_conf)
                if source not in sources:
                    sources.append(source)
            
            # Cap combined confidence at 0.98 to avoid overconfidence
            combined_conf = min(0.98, 1.0 - product)
            value_confidences.append((original_value, combined_conf, sources))
        
        # Sort by confidence (highest first)
        value_confidences.sort(key=lambda x: x[1], reverse=True)
        
        best_value, best_conf, best_sources = value_confidences[0]
        
        # Check for conflicts - flag when multiple distinct values have reasonable confidence
        has_conflict = False
        competing_values = []
        
        if len(value_confidences) > 1:
            # Conflict exists if any alternative value has confidence close to best
            for value, conf, _ in value_confidences[1:]:
                if conf >= self.CONFLICT_THRESHOLD:
                    # Also check if confidence is within 50% of best - indicates real disagreement
                    if conf >= best_conf * 0.5:
                        has_conflict = True
                    competing_values.append((value, round(conf, 2)))
        
        return ResolvedField(
            value=best_value,
            confidence=round(best_conf, 3),
            sources=best_sources,
            has_conflict=has_conflict,
            competing_values=competing_values
        )
    
    def clear_task(self, task_id: str) -> None:
        """Clear all data for a task"""
        if task_id in self._observations:
            del self._observations[task_id]
        if task_id in self._resolved_cache:
            del self._resolved_cache[task_id]
        logger.info(f"Cleared aggregation data for task {task_id}")


# Global instance
circuit_aggregation_service = CircuitAggregationService()


@dataclass
class ParameterValue:
    """A stored parameter value with confidence tracking"""
    value: Any
    confidence: float
    method: ExtractionMethod
    source_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def effective_confidence(self) -> float:
        """Calculate effective confidence considering method weight"""
        base_weight = METHOD_CONFIDENCE_WEIGHTS.get(self.method, 0.5)
        return min(1.0, self.confidence * base_weight)


class PanelParameterStore:
    """
    Confidence-aware storage for panel parameters (voltage, phase, wire, etc.).
    
    Parameters are only updated if the new confidence exceeds the existing confidence.
    This prevents lower-quality sources (e.g., text OCR) from overwriting higher-quality
    values (e.g., AI vision).
    
    Confidence weights:
    - AI vision: 0.85 (highest - visual nameplate detection)
    - manual: 0.70 (voice/text input from user)
    - AI OCR fallback: 0.70
    - text OCR: 0.60 (lowest)
    """
    
    # Parameters that support confidence tracking
    TRACKED_PARAMETERS = {
        'voltage', 'phase', 'wire', 'main_bus_amps', 'main_breaker',
        'mounting', 'feed', 'location', 'fed_from', 'panel_name',
        'short_circuit_rating', 'feed_thru_lugs'
    }
    
    def __init__(self):
        # Per-task parameter storage: task_id -> param_name -> ParameterValue
        self._store: Dict[str, Dict[str, ParameterValue]] = {}
    
    def get_parameter(self, task_id: str, param_name: str) -> Optional[ParameterValue]:
        """Get the current stored value for a parameter"""
        if task_id not in self._store:
            return None
        return self._store[task_id].get(param_name)
    
    def get_value(self, task_id: str, param_name: str) -> Optional[Any]:
        """Get just the value for a parameter (convenience method)"""
        param = self.get_parameter(task_id, param_name)
        return param.value if param else None
    
    def update_parameter(
        self,
        task_id: str,
        param_name: str,
        value: Any,
        confidence: float,
        method: ExtractionMethod,
        source_id: str = "unknown"
    ) -> Tuple[bool, Optional[str]]:
        """
        Update a parameter only if the new confidence exceeds existing.
        
        Args:
            task_id: The task identifier
            param_name: Parameter name (voltage, phase, etc.)
            value: The new value to set
            confidence: Raw confidence (0.0 to 1.0)
            method: Extraction method (determines weight)
            source_id: Source identifier (filename, "manual", etc.)
            
        Returns:
            Tuple of (was_updated, reason)
            - was_updated: True if the value was updated
            - reason: Explanation of why update was accepted or rejected
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, "Empty value ignored"
        
        if task_id not in self._store:
            self._store[task_id] = {}
        
        # Calculate effective confidence
        new_effective = min(1.0, confidence * METHOD_CONFIDENCE_WEIGHTS.get(method, 0.5))
        
        existing = self._store[task_id].get(param_name)
        
        if existing is None:
            # No existing value - accept the new one
            self._store[task_id][param_name] = ParameterValue(
                value=value,
                confidence=confidence,
                method=method,
                source_id=source_id
            )
            logger.info(
                f"[{task_id}] Set {param_name}='{value}' "
                f"(confidence={new_effective:.2f}, method={method.value}, source={source_id})"
            )
            return True, f"New parameter set with confidence {new_effective:.2f}"
        
        existing_effective = existing.effective_confidence()
        
        if new_effective > existing_effective:
            # New value has higher confidence - accept it
            old_value = existing.value
            self._store[task_id][param_name] = ParameterValue(
                value=value,
                confidence=confidence,
                method=method,
                source_id=source_id
            )
            logger.info(
                f"[{task_id}] Updated {param_name}: '{old_value}' -> '{value}' "
                f"(confidence {existing_effective:.2f} -> {new_effective:.2f}, "
                f"method={method.value}, source={source_id})"
            )
            return True, f"Updated: new confidence {new_effective:.2f} > existing {existing_effective:.2f}"
        else:
            # New value has equal or lower confidence - reject it
            logger.debug(
                f"[{task_id}] Rejected {param_name}='{value}' "
                f"(new confidence {new_effective:.2f} <= existing {existing_effective:.2f})"
            )
            return False, f"Rejected: new confidence {new_effective:.2f} <= existing {existing_effective:.2f}"
    
    def update_parameters_batch(
        self,
        task_id: str,
        params: Dict[str, Any],
        confidence: float,
        method: ExtractionMethod,
        source_id: str = "unknown"
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Update multiple parameters at once with the same confidence and method.
        
        Returns dict of param_name -> (was_updated, reason)
        """
        results = {}
        for param_name, value in params.items():
            # Only track parameters in the TRACKED_PARAMETERS set
            if param_name.lower() in self.TRACKED_PARAMETERS:
                was_updated, reason = self.update_parameter(
                    task_id, param_name.lower(), value, confidence, method, source_id
                )
                results[param_name] = (was_updated, reason)
        return results
    
    def get_all_parameters(self, task_id: str) -> Dict[str, Any]:
        """Get all current parameter values for a task (just values, no metadata)"""
        if task_id not in self._store:
            return {}
        return {
            param_name: pv.value 
            for param_name, pv in self._store[task_id].items()
        }
    
    def get_all_with_confidence(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all parameters with their confidence info"""
        if task_id not in self._store:
            return {}
        return {
            param_name: {
                'value': pv.value,
                'confidence': round(pv.effective_confidence(), 2),
                'method': pv.method.value,
                'source': pv.source_id
            }
            for param_name, pv in self._store[task_id].items()
        }
    
    def clear_task(self, task_id: str) -> None:
        """Clear all parameters for a task"""
        if task_id in self._store:
            del self._store[task_id]
            logger.info(f"Cleared parameter store for task {task_id}")


# Global instance for panel parameters
panel_parameter_store = PanelParameterStore()
