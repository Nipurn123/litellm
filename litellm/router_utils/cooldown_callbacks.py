"""
Callbacks triggered on cooling down deployments
"""

import copy
from typing import TYPE_CHECKING, Any, Optional, Union

import litellm
from litellm._logging import verbose_logger

if TYPE_CHECKING:
    from litellm.router import Router as _Router

    LitellmRouter = _Router
else:
    LitellmRouter = Any


async def router_cooldown_event_callback(
    litellm_router_instance: LitellmRouter,
    deployment_id: str,
    exception_status: Union[str, int],
    cooldown_time: float,
):
    """
    Callback triggered when a deployment is put into cooldown by litellm

    - Updates deployment state on Prometheus
    - Increments cooldown metric for deployment on Prometheus
    """
    verbose_logger.debug("In router_cooldown_event_callback - updating prometheus")
    _deployment = litellm_router_instance.get_deployment(model_id=deployment_id)
    if _deployment is None:
        verbose_logger.warning(
            f"in router_cooldown_event_callback but _deployment is None for deployment_id={deployment_id}. Doing nothing"
        )
        return
    _litellm_params = _deployment["litellm_params"]
    temp_litellm_params = copy.deepcopy(_litellm_params)
    temp_litellm_params = dict(temp_litellm_params)
    _model_name = _deployment.get("model_name", None) or ""
    _api_base = (
        litellm.get_api_base(model=_model_name, optional_params=temp_litellm_params)
        or ""
    )
    model_info = _deployment["model_info"]
    model_id = model_info.id

    litellm_model_name = temp_litellm_params.get("model") or ""
    llm_provider = ""
    try:
        _, llm_provider, _, _ = litellm.get_llm_provider(
            model=litellm_model_name,
            custom_llm_provider=temp_litellm_params.get("custom_llm_provider"),
        )
    except Exception:
        pass

    # Trigger cooldown on Prometheus
    from litellm.integrations.custom_logger import CustomLogger
    from litellm.integrations.prometheus import PrometheusLogger
    from litellm.litellm_core_utils.litellm_logging import (
        get_custom_logger_compatible_class,
    )

    # get the prometheus logger from in memory loggers
    prometheusLogger: Optional[CustomLogger] = get_custom_logger_compatible_class(
        logging_integration="prometheus",
    )

    if prometheusLogger is not None:

        if isinstance(prometheusLogger, PrometheusLogger):
            prometheusLogger.set_deployment_complete_outage(
                litellm_model_name=_model_name,
                model_id=model_id,
                api_base=_api_base,
                api_provider=llm_provider,
            )

            prometheusLogger.increment_deployment_cooled_down(
                litellm_model_name=_model_name,
                model_id=model_id,
                api_base=_api_base,
                api_provider=llm_provider,
                exception_status=str(exception_status),
            )

    return
