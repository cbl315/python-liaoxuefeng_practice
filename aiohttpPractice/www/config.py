# config.py
import config_dafault
configs = config_dafault.configs

try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass