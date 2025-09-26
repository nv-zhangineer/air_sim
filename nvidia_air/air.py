import air_sdk
from air_sdk import AirApi as AirApiV1  # Imports the original SDK
from air_sdk.v2 import AirApi as AirApiV2
import streamlit as st


class Air:
    def __init__(self, username, api_key, dot_file='', title='air lab', ztp_content=None):
        self.ztp_content = ztp_content
        self.dot_file = dot_file
        self.title = title
        self.username = username
        self.api_key = api_key
        self.airv1 = self._create_airv1()

    def _create_airv1(self):
        return AirApiV1(username=self.username, password=f'{self.api_key}')

    def create_airv2(self):
        return AirApiV2(username=self.username, password=f'{self.api_key}')

    def create_simulation(self):
        try:
            return self.airv1.simulations.create(topology_data=self.dot_file, title=self.title,
                                                 ztp_content=self.ztp_content)
        except air_sdk.AirUnexpectedResponse as air_error:
            st.error(air_error)

    def create_service(self, simulation, service_type='ssh'):
        if service_type == 'ssh':
            return self._create_oob_ssh_service(simulation, 'OOB SSH')

    def _create_oob_ssh_service(self, simulation: AirApiV1.simulation, service_name: str):
        return self.airv1.services.create(name=service_name,
                                          interface='oob-mgmt-server:eth0',
                                          simulation=simulation,
                                          dest_port=22)


class QueryAir:
    def __init__(self, username, api_key, title):
        self.username = username
        self.api_key = api_key
        self.airv1 = AirApiV1(username=self.username, password=f'{self.api_key}')
        self.title = title
        self.sim_id = self.get_simulation_id_with_title()

    def get_simulation_id_with_title(self):
        for sim in self.airv1.simulations.list():
            if self.title == sim.title:
                self.sim_id = sim.id
                return self.sim_id
        else:
            print(f"no simulations found with title {self.title}")
            return None

    def get_simulation_state(self):
        return self.airv1.simulation.get(self.sim_id).state

    def get_simulations(self):
        for sim in self.airv1.simulations.list():
            print(sim.json())

    def start_sim(self):
        try:
            return self.airv1.simulation.get(self.sim_id).start()
        except air_sdk.AirUnexpectedResponse as air_error:
            st.error(air_error)


def get_ztp_content():
    with open('nvidia_air/scripts/ztp.txt', 'r') as ztp_file:
        return ztp_file.read()

#
# if __name__ == '__main__':
#     load_dotenv()
#     # ztp_content = get_ztp_content()
#     dot_file_path = 'cumulus_ansible/roles/ptm/files/topology.dot'
#     sim_title = 'air simulation-testv3'
#     api_key = os.getenv('NVIDIA_AIR_API_KEY')
#     username = 'peter.zhang@wwt.com'
#     # air = Air(username=username, api_key=api_key, dot_file=dot_file_path,
#     #           title=sim_title)
#     # air_sim = air.create_simulation()
#     air_query = QueryAir(username=username, api_key=api_key, title=sim_title)
#     current_state = air_query.get_simulation_state()
#     while air_query.get_simulation_state() != "LOADED":
#         # air_query.start_sim()
#         print("trying to start simulation.....")
#         print(f"current state {air_query.get_simulation_state()}.....")
#         import time
#         time.sleep(5)
#         current_state = air_query.get_simulation_state()
#
#     # service = air.create_service(simulation=air_sim)
# #     print(
# #         f"""
# # ssh -p {service.src_port} {service.os_default_username}@{service.host}
# # scp -P {service.src_port} -r cumulus_ansible {service.os_default_username}@{service.host}:~/
# # scp -P {service.src_port} -r nvidia_air {service.os_default_username}@{service.host}:~/
# # ssh -p {service.src_port} {service.os_default_username}@{service.host} << EOF
# # sudo apt-get install expect -y
# # chmod 775 ~/nvidia_air/scripts/env_setup.sh
# # ./nvidia_air/scripts/env_setup.sh
# # EOF
# # """)
