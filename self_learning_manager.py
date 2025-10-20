"""
Self Learning Manager for DAP System
AI self-learning and model management

Provides comprehensive machine learning model management, training,
and continuous improvement capabilities for the DAP audit system.
"""

import asyncio
import json
import time
import uuid
import os
import pickle
import joblib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
import logging
from contextlib import asynccontextmanager
import numpy as np
import threading
from collections import defaultdict, deque

# Add project root to path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import tensorflow as tf
    from tensorflow import keras
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

class SelfLearningManager:
    """
    Self-learning AI manager for DAP system

    Features:
    - Model lifecycle management
    - Automated training and retraining
    - Performance monitoring and drift detection
    - Model versioning and rollback
    - Continuous learning from user feedback
    - Multi-algorithm ensemble management
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.setup_logging()

        # Model registry
        self.models = {}
        self.model_metadata = {}
        self.model_performance = {}

        # Learning configuration
        self.learning_enabled = self.config.get('learning_enabled', True)
        self.auto_retrain_threshold = self.config.get('auto_retrain_threshold', 0.05)  # 5% performance drop
        self.feedback_batch_size = self.config.get('feedback_batch_size', 100)
        self.model_save_path = self.config.get('model_save_path', 'models/')

        # Data management
        self.training_data = defaultdict(list)
        self.feedback_data = defaultdict(deque)
        self.validation_data = defaultdict(list)

        # Performance tracking
        self.performance_history = defaultdict(deque)
        self.drift_detection = {}

        # Training scheduler
        self.training_scheduler = {}
        self.training_queue = asyncio.Queue()
        self.training_active = False

        # Supported model types
        self.supported_models = {
            'anomaly_detection': ['isolation_forest', 'autoencoder', 'one_class_svm'],
            'classification': ['random_forest', 'neural_network', 'xgboost'],
            'regression': ['linear_regression', 'random_forest_regressor', 'neural_network'],
            'nlp': ['bert', 'transformer', 'text_classifier'],
            'clustering': ['kmeans', 'dbscan', 'hierarchical']
        }

        self.initialize_manager()

    def setup_logging(self):
        """Setup enhanced logging for self-learning manager"""
        self.logger = logging.getLogger(f"{__name__}.SelfLearningManager")

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def initialize_manager(self):
        """Initialize self-learning manager"""
        try:
            # Create model directory
            os.makedirs(self.model_save_path, exist_ok=True)

            # Initialize MLflow if available
            if MLFLOW_AVAILABLE:
                self.setup_mlflow()

            # Load existing models
            self.load_existing_models()

            # Initialize default models
            self.initialize_default_models()

            self.logger.info("Self-Learning Manager initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing Self-Learning Manager: {e}")

    def setup_mlflow(self):
        """Setup MLflow for experiment tracking"""
        try:
            mlflow.set_tracking_uri(self.config.get('mlflow_tracking_uri', 'sqlite:///mlflow.db'))
            mlflow.set_experiment(self.config.get('mlflow_experiment', 'dap_audit_models'))
            self.logger.info("MLflow configured for experiment tracking")
        except Exception as e:
            self.logger.error(f"Error setting up MLflow: {e}")

    def load_existing_models(self):
        """Load existing trained models from disk"""
        try:
            model_files = [f for f in os.listdir(self.model_save_path) if f.endswith('.pkl') or f.endswith('.joblib')]

            for model_file in model_files:
                try:
                    model_path = os.path.join(self.model_save_path, model_file)
                    model_name = os.path.splitext(model_file)[0]

                    # Load model
                    if model_file.endswith('.pkl'):
                        with open(model_path, 'rb') as f:
                            model = pickle.load(f)
                    else:
                        model = joblib.load(model_path)

                    self.models[model_name] = model

                    # Load metadata if exists
                    metadata_path = os.path.join(self.model_save_path, f"{model_name}_metadata.json")
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            self.model_metadata[model_name] = json.load(f)

                    self.logger.info(f"Loaded model: {model_name}")

                except Exception as e:
                    self.logger.error(f"Error loading model {model_file}: {e}")

        except Exception as e:
            self.logger.error(f"Error loading existing models: {e}")

    def initialize_default_models(self):
        """Initialize default models for audit tasks"""
        try:
            # Anomaly detection model for financial transactions
            if 'financial_anomaly_detector' not in self.models and SKLEARN_AVAILABLE:
                model = IsolationForest(
                    contamination=0.1,
                    random_state=42,
                    n_estimators=100
                )
                self.register_model(
                    'financial_anomaly_detector',
                    model,
                    'anomaly_detection',
                    'Detect anomalous financial transactions'
                )

            # Account classification model
            if 'account_classifier' not in self.models and SKLEARN_AVAILABLE:
                model = Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
                ])
                self.register_model(
                    'account_classifier',
                    model,
                    'classification',
                    'Classify chart of accounts'
                )

            # Risk assessment model
            if 'risk_assessor' not in self.models and SKLEARN_AVAILABLE:
                model = Pipeline([
                    ('scaler', StandardScaler()),
                    ('regressor', RandomForestClassifier(n_estimators=100, random_state=42))
                ])
                self.register_model(
                    'risk_assessor',
                    model,
                    'classification',
                    'Assess audit risk levels'
                )

            self.logger.info(f"Initialized {len(self.models)} default models")

        except Exception as e:
            self.logger.error(f"Error initializing default models: {e}")

    def register_model(self, name: str, model: Any, model_type: str, description: str, metadata: Dict[str, Any] = None):
        """Register a new model in the system"""
        try:
            self.models[name] = model

            self.model_metadata[name] = {
                'name': name,
                'type': model_type,
                'description': description,
                'created_at': datetime.now().isoformat(),
                'version': 1,
                'status': 'initialized',
                'performance': {},
                'training_history': [],
                **(metadata or {})
            }

            self.model_performance[name] = {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1_score': 0.0,
                'last_evaluated': None
            }

            self.logger.info(f"Registered model: {name} ({model_type})")

        except Exception as e:
            self.logger.error(f"Error registering model {name}: {e}")

    async def train_model(self, model_name: str, training_data: Dict[str, Any], validation_split: float = 0.2) -> Dict[str, Any]:
        """Train or retrain a specific model"""
        try:
            if model_name not in self.models:
                return {'error': f'Model {model_name} not found'}

            self.logger.info(f"Starting training for model: {model_name}")

            model = self.models[model_name]
            metadata = self.model_metadata[model_name]

            # Prepare training data
            X, y = self.prepare_training_data(training_data, metadata['type'])

            if X is None or len(X) == 0:
                return {'error': 'No valid training data provided'}

            # Split data for validation
            if len(X) > 1 and validation_split > 0:
                X_train, X_val, y_train, y_val = train_test_split(
                    X, y, test_size=validation_split, random_state=42
                )
            else:
                X_train, X_val, y_train, y_val = X, None, y, None

            # Start MLflow run if available
            mlflow_run = None
            if MLFLOW_AVAILABLE:
                mlflow_run = mlflow.start_run(run_name=f"{model_name}_training")

            training_start = time.time()

            # Train model based on type
            if metadata['type'] == 'anomaly_detection':
                training_result = await self.train_anomaly_model(model, X_train, model_name)
            elif metadata['type'] == 'classification':
                training_result = await self.train_classification_model(model, X_train, y_train, model_name)
            elif metadata['type'] == 'regression':
                training_result = await self.train_regression_model(model, X_train, y_train, model_name)
            elif metadata['type'] == 'nlp':
                training_result = await self.train_nlp_model(model, X_train, y_train, model_name)
            else:
                return {'error': f'Unsupported model type: {metadata["type"]}'}

            training_time = time.time() - training_start

            # Validate model if validation data available
            if X_val is not None and y_val is not None:
                validation_result = await self.validate_model(model, X_val, y_val, metadata['type'])
            else:
                validation_result = {}

            # Update model metadata
            metadata['version'] += 1
            metadata['status'] = 'trained'
            metadata['last_trained'] = datetime.now().isoformat()
            metadata['training_time'] = training_time
            metadata['training_samples'] = len(X_train)

            # Update performance metrics
            if validation_result:
                self.model_performance[model_name].update(validation_result)
                self.model_performance[model_name]['last_evaluated'] = datetime.now().isoformat()

            # Add to training history
            training_record = {
                'timestamp': datetime.now().isoformat(),
                'version': metadata['version'],
                'training_samples': len(X_train),
                'training_time': training_time,
                'performance': validation_result,
                **training_result
            }
            metadata['training_history'].append(training_record)

            # Save model
            await self.save_model(model_name)

            # Log to MLflow
            if MLFLOW_AVAILABLE and mlflow_run:
                mlflow.log_params({
                    'model_name': model_name,
                    'model_type': metadata['type'],
                    'training_samples': len(X_train)
                })
                if validation_result:
                    mlflow.log_metrics(validation_result)
                mlflow.end_run()

            result = {
                'model_name': model_name,
                'status': 'success',
                'version': metadata['version'],
                'training_time': training_time,
                'training_samples': len(X_train),
                'performance': validation_result
            }

            self.logger.info(f"Training completed for {model_name}: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Error training model {model_name}: {e}")
            if MLFLOW_AVAILABLE and mlflow_run:
                mlflow.end_run(status='FAILED')
            return {'error': str(e)}

    async def train_anomaly_model(self, model: Any, X_train: np.ndarray, model_name: str) -> Dict[str, Any]:
        """Train anomaly detection model"""
        try:
            # Fit the model (unsupervised learning)
            model.fit(X_train)

            # Calculate contamination score
            anomaly_scores = model.decision_function(X_train)
            contamination_rate = len(anomaly_scores[anomaly_scores < 0]) / len(anomaly_scores)

            return {
                'algorithm': type(model).__name__,
                'contamination_rate': contamination_rate,
                'training_method': 'unsupervised'
            }

        except Exception as e:
            self.logger.error(f"Error training anomaly model: {e}")
            return {'error': str(e)}

    async def train_classification_model(self, model: Any, X_train: np.ndarray, y_train: np.ndarray, model_name: str) -> Dict[str, Any]:
        """Train classification model"""
        try:
            # Fit the model
            model.fit(X_train, y_train)

            # Cross-validation if sklearn available
            if SKLEARN_AVAILABLE and hasattr(model, 'predict'):
                cv_scores = cross_val_score(model, X_train, y_train, cv=5)
                cv_mean = np.mean(cv_scores)
                cv_std = np.std(cv_scores)
            else:
                cv_mean, cv_std = 0.0, 0.0

            return {
                'algorithm': type(model).__name__,
                'cv_accuracy_mean': cv_mean,
                'cv_accuracy_std': cv_std,
                'training_method': 'supervised',
                'n_classes': len(np.unique(y_train))
            }

        except Exception as e:
            self.logger.error(f"Error training classification model: {e}")
            return {'error': str(e)}

    async def train_regression_model(self, model: Any, X_train: np.ndarray, y_train: np.ndarray, model_name: str) -> Dict[str, Any]:
        """Train regression model"""
        try:
            # Fit the model
            model.fit(X_train, y_train)

            # Calculate R² score
            if hasattr(model, 'score'):
                r2_score = model.score(X_train, y_train)
            else:
                r2_score = 0.0

            return {
                'algorithm': type(model).__name__,
                'r2_score': r2_score,
                'training_method': 'supervised'
            }

        except Exception as e:
            self.logger.error(f"Error training regression model: {e}")
            return {'error': str(e)}

    async def train_nlp_model(self, model: Any, X_train: List[str], y_train: List[str], model_name: str) -> Dict[str, Any]:
        """Train NLP model"""
        try:
            # This is a placeholder for NLP model training
            # In a real implementation, this would handle text preprocessing,
            # tokenization, and training of transformer models

            return {
                'algorithm': 'NLP_Model',
                'training_method': 'supervised',
                'vocab_size': len(set(' '.join(X_train).split())),
                'training_samples': len(X_train)
            }

        except Exception as e:
            self.logger.error(f"Error training NLP model: {e}")
            return {'error': str(e)}

    def prepare_training_data(self, training_data: Dict[str, Any], model_type: str) -> Tuple[Any, Any]:
        """Prepare training data based on model type"""
        try:
            if not PANDAS_AVAILABLE:
                # Simple numpy-based preparation
                X = np.array(training_data.get('features', []))
                y = np.array(training_data.get('labels', []))
                return X, y

            # Pandas-based preparation
            if 'dataframe' in training_data:
                df = pd.DataFrame(training_data['dataframe'])
            else:
                df = pd.DataFrame({
                    'features': training_data.get('features', []),
                    'labels': training_data.get('labels', [])
                })

            if df.empty:
                return None, None

            # Prepare features
            feature_columns = training_data.get('feature_columns', [col for col in df.columns if col != 'labels'])
            X = df[feature_columns].values

            # Prepare labels
            if model_type == 'anomaly_detection':
                y = None  # Unsupervised learning
            else:
                y = df.get('labels', pd.Series()).values if 'labels' in df.columns else None

            return X, y

        except Exception as e:
            self.logger.error(f"Error preparing training data: {e}")
            return None, None

    async def validate_model(self, model: Any, X_val: np.ndarray, y_val: np.ndarray, model_type: str) -> Dict[str, Any]:
        """Validate model performance"""
        try:
            if not hasattr(model, 'predict'):
                return {}

            if model_type == 'anomaly_detection':
                # Anomaly detection validation
                predictions = model.predict(X_val)
                anomaly_rate = len(predictions[predictions == -1]) / len(predictions)
                return {'anomaly_rate': anomaly_rate}

            elif model_type in ['classification', 'nlp']:
                # Classification validation
                y_pred = model.predict(X_val)

                if SKLEARN_AVAILABLE:
                    accuracy = accuracy_score(y_val, y_pred)
                    precision = precision_score(y_val, y_pred, average='weighted', zero_division=0)
                    recall = recall_score(y_val, y_pred, average='weighted', zero_division=0)
                    f1 = f1_score(y_val, y_pred, average='weighted', zero_division=0)

                    return {
                        'accuracy': accuracy,
                        'precision': precision,
                        'recall': recall,
                        'f1_score': f1
                    }
                else:
                    # Simple accuracy calculation
                    accuracy = np.mean(y_pred == y_val)
                    return {'accuracy': accuracy}

            elif model_type == 'regression':
                # Regression validation
                y_pred = model.predict(X_val)
                mse = np.mean((y_val - y_pred) ** 2)
                mae = np.mean(np.abs(y_val - y_pred))

                return {
                    'mse': mse,
                    'mae': mae,
                    'rmse': np.sqrt(mse)
                }

            return {}

        except Exception as e:
            self.logger.error(f"Error validating model: {e}")
            return {'error': str(e)}

    async def predict(self, model_name: str, input_data: Any, return_confidence: bool = False) -> Dict[str, Any]:
        """Make predictions using a specific model"""
        try:
            if model_name not in self.models:
                return {'error': f'Model {model_name} not found'}

            model = self.models[model_name]
            metadata = self.model_metadata[model_name]

            # Prepare input data
            X = self.prepare_input_data(input_data, metadata['type'])

            if X is None:
                return {'error': 'Invalid input data'}

            # Make prediction
            if hasattr(model, 'predict'):
                predictions = model.predict(X)
            else:
                return {'error': 'Model does not support prediction'}

            result = {
                'model_name': model_name,
                'predictions': predictions.tolist() if hasattr(predictions, 'tolist') else predictions
            }

            # Add confidence scores if available and requested
            if return_confidence and hasattr(model, 'predict_proba'):
                try:
                    probabilities = model.predict_proba(X)
                    result['confidence'] = probabilities.tolist()
                except:
                    pass

            # Add decision function scores for anomaly detection
            if metadata['type'] == 'anomaly_detection' and hasattr(model, 'decision_function'):
                try:
                    scores = model.decision_function(X)
                    result['anomaly_scores'] = scores.tolist()
                except:
                    pass

            return result

        except Exception as e:
            self.logger.error(f"Error making prediction with {model_name}: {e}")
            return {'error': str(e)}

    def prepare_input_data(self, input_data: Any, model_type: str) -> Optional[np.ndarray]:
        """Prepare input data for prediction"""
        try:
            if isinstance(input_data, np.ndarray):
                return input_data
            elif isinstance(input_data, list):
                return np.array(input_data)
            elif isinstance(input_data, dict):
                if 'features' in input_data:
                    return np.array(input_data['features'])
                else:
                    # Convert dict to feature array
                    return np.array(list(input_data.values())).reshape(1, -1)
            elif PANDAS_AVAILABLE and isinstance(input_data, pd.DataFrame):
                return input_data.values
            else:
                return np.array([input_data]).reshape(1, -1)

        except Exception as e:
            self.logger.error(f"Error preparing input data: {e}")
            return None

    async def add_feedback(self, model_name: str, input_data: Any, expected_output: Any, actual_output: Any, feedback_type: str = 'correction'):
        """Add user feedback for continuous learning"""
        try:
            if model_name not in self.models:
                self.logger.warning(f"Feedback for unknown model: {model_name}")
                return

            feedback_entry = {
                'timestamp': datetime.now().isoformat(),
                'input_data': input_data,
                'expected_output': expected_output,
                'actual_output': actual_output,
                'feedback_type': feedback_type,
                'processed': False
            }

            self.feedback_data[model_name].append(feedback_entry)

            # Trigger retraining if enough feedback accumulated
            if len(self.feedback_data[model_name]) >= self.feedback_batch_size:
                await self.queue_retraining(model_name)

            self.logger.info(f"Added feedback for model {model_name}: {feedback_type}")

        except Exception as e:
            self.logger.error(f"Error adding feedback: {e}")

    async def queue_retraining(self, model_name: str):
        """Queue model for retraining"""
        try:
            await self.training_queue.put({
                'model_name': model_name,
                'reason': 'feedback_accumulation',
                'timestamp': datetime.now().isoformat()
            })

            self.logger.info(f"Queued {model_name} for retraining")

        except Exception as e:
            self.logger.error(f"Error queuing retraining: {e}")

    async def process_feedback_batch(self, model_name: str) -> Dict[str, Any]:
        """Process accumulated feedback for a model"""
        try:
            if model_name not in self.feedback_data:
                return {'error': 'No feedback data available'}

            feedback_list = list(self.feedback_data[model_name])
            if not feedback_list:
                return {'message': 'No feedback to process'}

            # Convert feedback to training data
            training_data = {
                'features': [],
                'labels': []
            }

            for feedback in feedback_list:
                if feedback['feedback_type'] == 'correction':
                    training_data['features'].append(feedback['input_data'])
                    training_data['labels'].append(feedback['expected_output'])

            if training_data['features']:
                # Retrain model with feedback data
                result = await self.train_model(model_name, training_data)

                # Mark feedback as processed
                for feedback in feedback_list:
                    feedback['processed'] = True

                return result
            else:
                return {'message': 'No valid feedback for training'}

        except Exception as e:
            self.logger.error(f"Error processing feedback batch: {e}")
            return {'error': str(e)}

    async def detect_model_drift(self, model_name: str, recent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect performance drift in model"""
        try:
            if model_name not in self.models:
                return {'error': f'Model {model_name} not found'}

            model = self.models[model_name]
            metadata = self.model_metadata[model_name]
            current_performance = self.model_performance[model_name]

            # Prepare recent data for validation
            X, y = self.prepare_training_data(recent_data, metadata['type'])

            if X is None or y is None:
                return {'error': 'Invalid recent data for drift detection'}

            # Evaluate model on recent data
            recent_performance = await self.validate_model(model, X, y, metadata['type'])

            if not recent_performance or 'accuracy' not in recent_performance:
                return {'message': 'Cannot detect drift - insufficient performance data'}

            # Compare with baseline performance
            baseline_accuracy = current_performance.get('accuracy', 0)
            recent_accuracy = recent_performance.get('accuracy', 0)

            drift_magnitude = baseline_accuracy - recent_accuracy
            drift_detected = drift_magnitude > self.auto_retrain_threshold

            drift_result = {
                'model_name': model_name,
                'drift_detected': drift_detected,
                'drift_magnitude': drift_magnitude,
                'baseline_accuracy': baseline_accuracy,
                'recent_accuracy': recent_accuracy,
                'threshold': self.auto_retrain_threshold,
                'timestamp': datetime.now().isoformat()
            }

            # Store drift detection result
            if model_name not in self.drift_detection:
                self.drift_detection[model_name] = deque(maxlen=100)
            self.drift_detection[model_name].append(drift_result)

            # Queue for retraining if drift detected
            if drift_detected:
                await self.queue_retraining(model_name)
                self.logger.warning(f"Performance drift detected for {model_name}: {drift_magnitude:.3f}")

            return drift_result

        except Exception as e:
            self.logger.error(f"Error detecting model drift: {e}")
            return {'error': str(e)}

    async def save_model(self, model_name: str):
        """Save model and metadata to disk"""
        try:
            if model_name not in self.models:
                return

            model = self.models[model_name]
            metadata = self.model_metadata[model_name]

            # Save model
            model_path = os.path.join(self.model_save_path, f"{model_name}.joblib")
            joblib.dump(model, model_path)

            # Save metadata
            metadata_path = os.path.join(self.model_save_path, f"{model_name}_metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Saved model: {model_name}")

        except Exception as e:
            self.logger.error(f"Error saving model {model_name}: {e}")

    async def start_training_worker(self):
        """Start background training worker"""
        self.training_active = True

        while self.training_active:
            try:
                # Wait for training request
                training_request = await asyncio.wait_for(
                    self.training_queue.get(),
                    timeout=5.0
                )

                model_name = training_request['model_name']
                reason = training_request['reason']

                self.logger.info(f"Processing training request for {model_name} (reason: {reason})")

                if reason == 'feedback_accumulation':
                    # Process feedback and retrain
                    result = await self.process_feedback_batch(model_name)
                    self.logger.info(f"Feedback processing result for {model_name}: {result}")

                elif reason == 'drift_detection':
                    # Retrain with latest data
                    # This would need to be connected to actual data source
                    self.logger.info(f"Drift-based retraining for {model_name} - needs data connection")

                elif reason == 'scheduled':
                    # Scheduled retraining
                    self.logger.info(f"Scheduled retraining for {model_name} - needs data connection")

            except asyncio.TimeoutError:
                # No training requests, continue
                continue

            except Exception as e:
                self.logger.error(f"Error in training worker: {e}")
                await asyncio.sleep(5)

    async def stop_training_worker(self):
        """Stop background training worker"""
        self.training_active = False

    def get_model_status(self, model_name: str = None) -> Dict[str, Any]:
        """Get status of specific model or all models"""
        try:
            if model_name:
                if model_name not in self.models:
                    return {'error': f'Model {model_name} not found'}

                return {
                    'model_name': model_name,
                    'metadata': self.model_metadata[model_name],
                    'performance': self.model_performance[model_name],
                    'feedback_count': len(self.feedback_data.get(model_name, [])),
                    'drift_history': list(self.drift_detection.get(model_name, []))
                }
            else:
                return {
                    'total_models': len(self.models),
                    'models': {
                        name: {
                            'type': metadata['type'],
                            'status': metadata['status'],
                            'version': metadata['version'],
                            'performance': self.model_performance.get(name, {}),
                            'feedback_count': len(self.feedback_data.get(name, []))
                        }
                        for name, metadata in self.model_metadata.items()
                    },
                    'training_queue_size': self.training_queue.qsize(),
                    'training_active': self.training_active
                }

        except Exception as e:
            self.logger.error(f"Error getting model status: {e}")
            return {'error': str(e)}

    def generate_learning_report(self) -> Dict[str, Any]:
        """Generate comprehensive learning and performance report"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_models': len(self.models),
                    'trained_models': len([m for m in self.model_metadata.values() if m['status'] == 'trained']),
                    'total_feedback': sum(len(feedback) for feedback in self.feedback_data.values()),
                    'drift_detections': sum(len(drift) for drift in self.drift_detection.values())
                },
                'models': {},
                'recommendations': []
            }

            # Add model details
            for name, metadata in self.model_metadata.items():
                performance = self.model_performance.get(name, {})
                model_report = {
                    'type': metadata['type'],
                    'status': metadata['status'],
                    'version': metadata['version'],
                    'last_trained': metadata.get('last_trained'),
                    'performance': performance,
                    'feedback_count': len(self.feedback_data.get(name, [])),
                    'training_history_count': len(metadata.get('training_history', []))
                }

                # Add drift information
                if name in self.drift_detection:
                    recent_drift = list(self.drift_detection[name])[-1] if self.drift_detection[name] else None
                    if recent_drift:
                        model_report['latest_drift'] = recent_drift

                report['models'][name] = model_report

            # Generate recommendations
            recommendations = []

            # Check for models needing retraining
            for name, metadata in self.model_metadata.items():
                if metadata['status'] == 'initialized':
                    recommendations.append(f"Model '{name}' needs initial training")

                feedback_count = len(self.feedback_data.get(name, []))
                if feedback_count >= self.feedback_batch_size:
                    recommendations.append(f"Model '{name}' has {feedback_count} feedback items ready for retraining")

                # Check for outdated models
                if 'last_trained' in metadata:
                    last_trained = datetime.fromisoformat(metadata['last_trained'])
                    days_since_training = (datetime.now() - last_trained).days
                    if days_since_training > 30:
                        recommendations.append(f"Model '{name}' hasn't been retrained for {days_since_training} days")

            if not recommendations:
                recommendations.append("All models are up to date and performing well")

            report['recommendations'] = recommendations

            return report

        except Exception as e:
            self.logger.error(f"Error generating learning report: {e}")
            return {'error': str(e)}

# Test and main execution
async def test_self_learning_manager():
    """Test self-learning manager functionality"""
    print("Testing Self-Learning Manager...")

    manager = SelfLearningManager()
    print(f"✓ Manager initialized with {len(manager.models)} models")

    # Test model registration
    if SKLEARN_AVAILABLE:
        from sklearn.ensemble import RandomForestClassifier
        test_model = RandomForestClassifier(n_estimators=10, random_state=42)
        manager.register_model(
            'test_classifier',
            test_model,
            'classification',
            'Test classification model'
        )
        print("✓ Test model registered")

        # Test training
        training_data = {
            'features': [[1, 2], [2, 3], [3, 4], [4, 5]],
            'labels': [0, 0, 1, 1]
        }
        result = await manager.train_model('test_classifier', training_data)
        print(f"✓ Model training: {result.get('status')}")

        # Test prediction
        prediction = await manager.predict('test_classifier', [[2.5, 3.5]])
        print(f"✓ Prediction: {prediction.get('predictions')}")

    # Test status
    status = manager.get_model_status()
    print(f"✓ System status: {status['total_models']} models")

    # Test report
    report = manager.generate_learning_report()
    print(f"✓ Learning report: {len(report.get('recommendations', []))} recommendations")

    print("✓ Self-Learning Manager test completed")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DAP Self-Learning Manager')
    parser.add_argument('--train-models', '-t', action='store_true', help='Train all models')
    parser.add_argument('--start-worker', '-w', action='store_true', help='Start training worker')
    parser.add_argument('--report', '-r', action='store_true', help='Generate learning report')
    parser.add_argument('--status', '-s', action='store_true', help='Show model status')
    parser.add_argument('--test', action='store_true', help='Run test mode')

    args = parser.parse_args()

    async def main():
        manager = SelfLearningManager()

        if args.test:
            await test_self_learning_manager()

        elif args.report:
            report = manager.generate_learning_report()
            print(json.dumps(report, indent=2, ensure_ascii=False))

        elif args.status:
            status = manager.get_model_status()
            print(json.dumps(status, indent=2, ensure_ascii=False))

        elif args.train_models:
            print("Training all models...")
            for model_name in manager.models:
                print(f"Training {model_name}...")
                # This would need actual training data
                print(f"Model {model_name} - training data needed")

        elif args.start_worker:
            print("Starting training worker...")
            await manager.start_training_worker()

        else:
            print("DAP Self-Learning Manager")
            print("Use --train-models to train all models, --start-worker for background training, or --test for testing")
            print("Example: python self_learning_manager.py --start-worker")

    asyncio.run(main())