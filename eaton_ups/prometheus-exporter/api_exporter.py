"""Create and run a prometheus prometheus-exporter for a UPS device."""
import argparse
import time
import getpass

from api_scraper import UPSScraper
from prometheus_client import start_http_server, REGISTRY
from prometheus_client.core import GaugeMetricFamily


class UPSExporter:

    def __init__(
            self,
            ups_address,
            username,
            password,
            insecure):
        """Create an UPS prometheus prometheus-exporter."""
        self.ups_scraper = UPSScraper(
            ups_address,
            username,
            password,
            insecure
        )

    def collect(self):
        """Export UPS metrics on request."""

        ups_data = self.scrape_data()
        for measures in ups_data:
            ups_id = measures.get('ups_id')
            inputs = measures.get('ups_inputs')
            outputs = measures.get('ups_outputs')
            powerbank_details = measures.get('ups_powerbank')
            inputs_rm = inputs['measures']['realtime']
            outputs_rm = outputs['measures']['realtime']
            powerbank_m = powerbank_details['measures']
            powerbank_s = powerbank_details['status']

            relevant_measures = {
                "ups_input_voltage_in_volt":
                    inputs_rm['voltage'],
                "ups_input_frequency_in_herz":
                    inputs_rm['frequency'],
                "ups_input_current_in_ampere":
                    inputs_rm['current'],
                "ups_output_voltage_in_volt":
                    outputs_rm['voltage'],
                "ups_output_frequency_in_herz":
                    outputs_rm['frequency'],
                "ups_output_current_in_ampere":
                    outputs_rm['current'],
                "ups_output_apparent_power_in_voltampere":
                    outputs_rm['apparentPower'],
                "ups_output_active_power_in_watt":
                    outputs_rm['activePower'],
                "ups_output_power_factor":
                    outputs_rm['powerFactor'],
                "ups_output_percent_load_in_percent":
                    outputs_rm['percentLoad'],
                "ups_battery_voltage_in_volt":
                    powerbank_m['voltage'],
                "ups_battery_capacity_in_percent":
                    powerbank_m['remainingChargeCapacity'],
                "ups_battery_remaining_time":
                    powerbank_m['remainingTime'],
                "ups_battery_health":
                    powerbank_s['health']
            }

            for measure_label, value in relevant_measures.items():

                g = GaugeMetricFamily(
                    measure_label,
                    'Measure collected from the ups device',
                    labels=['ups_id']
                )
                g.add_metric([ups_id], value)
                yield g

    def scrape_data(self) -> list:
        return [self.ups_scraper.get_measures()]


class UPSMultiExporter(UPSExporter):
    """
    Prometheus exporter for multiple UPS devices.

    Collects metrics from multiple PDUs at the same time. If threading is
    enabled, multiple threads will be used to collect sensor readings which is
    considerably faster.

    Parameters
    ----------
    config : str
        Path to the configuration file, containing PDU location, username,
        and password combinations for all PDUs to be monitored
    threading : bool, optional
        Whether to use multithreading or serial processing. Note that serial
        processing becomes slower when more PDUs are added. Since the HTTP
        request to the json-rpc API and waiting for its response takes longest,
        threading is recommended when more than 1 PDU is being monitored
    insecure : bool, optional
        Whether to allow a connection to an insecure raritan API

    """

    def __init__(self, config=str, threading=False,insecure=False):
        pass

    def get_ups_devices(self):
        pass

    def scrape_data(self) -> list:
        pass





def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prometheus prometheus-exporter for Eaton UPS measures"
    )

    parser.add_argument(
        "address",
        help="Specify the address of the UPS device"
    )
    parser.add_argument(
        "-u", "--username",
        help="Specify a user name",
        required=True
    )
    parser.add_argument(
        "-p", "--port",
        help="Listen to this port",
        default=8000
    )
    parser.add_argument(
        "--host-address",
        help="Address by which the prometheus metrics will be accessible",
        default="127.0.0.1"
    )
    parser.add_argument(
        '-k', '--insecure',
        action='store_true',
        help='allow a connection to an insecure UPS API',
        default=False
    )

    return parser.parse_args()


if __name__ == '__main__':
    try:
        args = parse_args()
        pswd = getpass.getpass('Password:')
        port = int(args.port)
        ups_exporter = UPSExporter(
            args.address,
            args.username,
            pswd,
            insecure=args.insecure
        )

        REGISTRY.register(
            ups_exporter
        )

        # Start up the server to expose the metrics.
        start_http_server(port, addr=args.host_address)
        print(f"Starting Prometheus prometheus-exporter on {args.host_address}:{port}")
        while True:
            time.sleep(1)

    except TypeError as err:
        print(err)

    except KeyboardInterrupt:
        print("Prometheus prometheus-exporter shut down")
        exit(0)