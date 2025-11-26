from loguru import logger
from celery_singleton import Singleton
from packages.jobs.base import BaseTaskContext
from packages.jobs.celery_app import celery_app
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.storage.repositories import get_connection_params, ClientFactory
from packages.storage.repositories.transfer_repository import TransferRepository
from packages.storage.repositories.synthetic_transfer_repository import SyntheticTransferRepository
from packages.storage.repositories.ground_truth_repository import GroundTruthRepository
from packages.storage.repositories.address_label_repository import AddressLabelRepository
from packages import setup_logger
from packages.utils import calculate_time_window
from packages.evaluation.risk_evaluator import RiskEvaluator
from packages.evaluation.synthetic.injector import PatternInjector
from packages.evaluation.synthetic.generators import PatternGenerator


class ProduceSyntheticsTask(BaseDataPipelineTask, Singleton):

    def execute_task(self, context: BaseTaskContext):

        service_name = f'synthetics-{context.network}-produce'
        setup_logger(service_name)

        connection_params = get_connection_params(context.network)

        client_factory = ClientFactory(connection_params)
        with client_factory.client_context() as client:
            transfer_repository = TransferRepository(client)
            synthetics_transfer_repository = SyntheticTransferRepository(client)
            ground_truth_repository = GroundTruthRepository(client)
            address_label_repository = AddressLabelRepository(client)
            pattern_generator = PatternGenerator()
            injector = PatternInjector(
                transfer_repository=transfer_repository,
                pattern_generator=pattern_generator,
                network=context.network
            )

            logger.info(
                "Cleaning feature partition",
                extra={
                    "network": context.network,
                    "window_days": context.window_days,
                    "processing_date": context.processing_date
                }
            )
            synthetics_transfer_repository.delete_partition(context.window_days, context.processing_date)
            start_timestamp, end_timestamp = calculate_time_window(context.window_days, context.processing_date)

            logger.info(
                "Starting chain synthetics generation",
                extra={
                    "network": context.network,
                    "window_days": context.window_days,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                    "batch_size": context.batch_size
                }
            )

            evaluator = RiskEvaluator(
                transfer_repository=transfer_repository,
                synthetic_transfer_repository=synthetics_transfer_repository,
                ground_truth_repository=ground_truth_repository,
                address_label_repository=address_label_repository,
                injector=injector,
                network=context.network
            )
            
            # Calculate dynamic load based on network traffic
            stats = transfer_repository.get_global_stats()
            total_tx = stats.get('total_tx_count', 0)
            
            # Target ~2% of total volume as synthetic
            # Average 20 tx per hack instance estimation
            target_synthetic_volume = max(50, total_tx * 0.02)
            estimated_tx_per_hack = 20
            dynamic_num_hacks = max(1, int(target_synthetic_volume / estimated_tx_per_hack))
            
            # Cap at 500 to avoid explosion on huge networks during initial tests
            dynamic_num_hacks = min(500, dynamic_num_hacks)

            logger.info(
                f"Adjusting synthetic load: Total Real={total_tx}, Target Syn={target_synthetic_volume}, Num Hacks={dynamic_num_hacks}"
            )
            
            generated_df = evaluator.generate_challenge(
                num_hacks=dynamic_num_hacks,
                window_days=context.window_days,
                processing_date=context.processing_date
            )

            logger.success(
                f"Synthetics production completed. Generated {len(generated_df)} transactions.",
                extra={
                    "network": context.network,
                    "window_days": context.window_days
                }
            )

@celery_app.task(
    bind=True,
    base=ProduceSyntheticsTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 24,
        'countdown': 600
    },
    time_limit=7200,
    soft_time_limit=7080
)
def produce_synthetics_task(
    self,
    network: str,
    window_days: int,
    processing_date: str
):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date,
    )

    return self.run(context)


