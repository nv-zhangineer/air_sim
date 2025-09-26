import pytest
from util.spectrumx_netmapper import NetworkMapping
import ipaddress
import json

@pytest.mark.parametrize(
    "x, pod_id, su_id, rail_id, host_id, expected_nic_ip, expected_switch_ip",
    [
        (172, 0, 0, 3, 30, '172.96.0.60', '172.96.0.61'),  # 172.01100000.00000000.00111100
        (172, 0, 0, 4, 10, '172.128.0.20', '172.128.0.21'),  # 172.10000000.00000000.00010100
        (192, 0, 0, 7, 5, '192.224.0.10', '192.224.0.11')  # 172.11100000.00000000.00001010
    ]
)
def test_generate_host_ip(x, pod_id, su_id, rail_id, host_id, expected_nic_ip, expected_switch_ip):
    mapper = NetworkMapping(0)  # num_hosts not needed for this test
    nic_ip, switch_ip = mapper._generate_host_ip(x, pod_id, su_id, rail_id, host_id)
    assert str(nic_ip) == expected_nic_ip
    assert str(switch_ip) == expected_switch_ip


@pytest.mark.parametrize(
    "num_hosts, expected_num_spines",
    [
        (32, 0),
        (64, 4),
        (96, 8),
        (128, 8),
        (1024, 64)
    ]
)
def test_calculate_num_spines(num_hosts, expected_num_spines):
    mapper = NetworkMapping(int(num_hosts))
    num_spines = mapper.num_spines
    assert num_spines == expected_num_spines


def test_generate_host_ip_raise_error():
    # Assert that generate_host_ip function raises a value error when exceeding 8 bits
    mapper = NetworkMapping(32)
    with pytest.raises(ValueError):
        mapper._generate_host_ip(192, 0, 0, 7, 32)


def test_create_leaf_host_port_mapping_1_tier_non_air():
    mapper = NetworkMapping(num_hosts=64, nvidia_air=False)
    result = mapper.leaf_host_mapping_data

    # Check total rows in result for 1 SU and 8 hosts
    assert len(result) == 512

    # Validate specific rows in the result
    assert result[0] == {
        "SU": 0,
        "Rail": 0,
        "HostID": 0,
        "HostName": "dgx000",
        "HostIntf": "rail1",
        "HostIntfIP": "172.0.0.0",
        "LeafID": 0,
        "LeafName": "leaf000",
        "LeafIntf": "swp1s0",
        "LeafIntfIP": "172.0.0.1",
        "Mask": "/31",
        "Description": "dgx000-rail1"
    }

    assert result[1] == {
        "SU": 0,
        "Rail": 1,
        "HostID": 0,
        "HostName": "dgx000",
        "HostIntf": "rail2",
        "HostIntfIP": "172.32.0.0",
        "LeafID": 0,
        "LeafName": "leaf000",
        "LeafIntf": "swp1s1",
        "LeafIntfIP": "172.32.0.1",
        "Mask": "/31",
        "Description": "dgx000-rail2"
    }

    assert result[63] == {
        "SU": 0,
        "Rail": 7,
        "HostID": 7,
        "HostName": "dgx007",
        "HostIntf": "rail8",
        "HostIntfIP": "172.224.0.14",  # 172.11100000.0.000001110
        "LeafID": 3,
        "LeafName": "leaf003",
        "LeafIntf": "swp8s1",
        "LeafIntfIP": "172.224.0.15",
        "Mask": "/31",
        "Description": "dgx007-rail8"
    }

    assert result[400] == {
        "SU": 1,        # 401 // ( 32 * 8 )
        "Rail": 0,      # 401 % 8 - 1 , rail ID starts at 0
        "HostID": 50,   # 401 // 8
        "HostName": "dgx050",
        "HostIntf": "rail1",     # railID + 1
        "HostIntfIP": "172.0.1.36",  # 172.00000000.00000001.00100110  # hostID = 50 % 32 = 18
        "LeafID": 4,    # since host ID = 50, it's nodeID is 18 within the SU, but also the 19th node.
                        # each node consumes 2 switch ports, so the next available interface starts at 37
                        # the leaf range is 04 - 07 because 401 // 64 = 6, so it falls between 04 - 07
                        # rail1-2 always connects to switch#1 in the SU
                        # rail3-4 always connects to switch#2 in the SU
        "LeafName": "leaf004",
        "LeafIntf": "swp19s0",
        "LeafIntfIP": "172.0.1.37",
        "Mask": "/31",
        "Description": "dgx050-rail1"
    }

    assert result[-1] == {
        "SU": 1,
        "Rail": 7,
        "HostID": 63,
        "HostName": "dgx063",
        "HostIntf": "rail8",
        "HostIntfIP": "172.224.1.62",  # 172.11100000.00000001.00111110
        "LeafID": 7,
        "LeafName": "leaf007",
        "LeafIntf": "swp32s1",
        "LeafIntfIP": "172.224.1.63",
        "Mask": "/31",
        "Description": "dgx063-rail8"
    }


def test_create_host_port_mapping_2_tier_non_air():
    mapper = NetworkMapping(num_hosts=896, nvidia_air=False)
    result = mapper.leaf_host_mapping_data

    # Check total rows in result for 28 SUs and 896 (maxed out 32 hosts per SU) hosts
    assert len(result) == 7168

    assert result[0] == {
        "SU": 0,
        "Rail": 0,
        "HostID": 0,
        "HostName": "dgx000",
        "HostIntf": "rail1",
        "HostIntfIP": "172.0.0.0",
        "LeafID": 0,
        "LeafName": "leaf000",
        "LeafIntf": "swp1s0",
        "LeafIntfIP": "172.0.0.1",
        "Mask": "/31",
        "Description": "dgx000-rail1"
    }

    assert result[1] == {
        "SU": 0,
        "Rail": 1,
        "HostID": 0,
        "HostName": "dgx000",
        "HostIntf": "rail2",
        "HostIntfIP": "172.32.0.0",
        "LeafID": 0,
        "LeafName": "leaf000",
        "LeafIntf": "swp1s1",
        "LeafIntfIP": "172.32.0.1",
        "Mask": "/31",
        "Description": "dgx000-rail2"
    }

    # Validate specific rows in the result
    assert result[5678] == {    # 5678 refers to 5680 in the spreadsheet
        "SU": 22,       # 5678 // ( 32 * 8 )
        "Rail": 6,      # 5679 % 8 - 1 , rail ID starts at 0
        "HostID": 709,  # 5679 // 8, local hostID = 709 % 32 = 5
        "HostName": "dgx709",
        "HostIntf": "rail7",   # railID + 1
        "HostIntfIP": "172.192.22.10",  # 172.11000000.00010110.00001010
        "LeafID": 91,   # local hostID = 5, but also the 6th node. it will start with interface 11
                        # the leaf range is 88 -> 91 because 401 // 64 = 88
                        # rail1-2 always connects to switch#1 in the SU
                        # rail3-4 always connects to switch#2 in the SU... etc.
                        # since we have hostIntf = 7, it connects to the 4th switch, which is 91
        "LeafName": "leaf091",
        "LeafIntf": "swp6s0",
        "LeafIntfIP": "172.192.22.11",
        "Mask": "/31",
        "Description": "dgx709-rail7"
    }


def test_create_leaf_spine_port_mapping_64_hosts():
    mapper = NetworkMapping(64)
    result = mapper.leaf_spine_mapping_data

    # total rows with 64 hosts, 8 leafs, 4 spines
    assert len(result) == 512   # 64 ports per leaf towards spine

    # Validate specific rows in the result2
    assert result[0] == {
        "SU": 0,
        "SpineID": 0,
        "SpineName": "spine000",
        "SpineIntf": "swp1",
        "SpineIntfIP": "10.254.0.0",
        "SpineAS": 65200,
        "LeafID": 0,
        "LeafName": "leaf000",
        "LeafIntf": "swp65",
        "LeafIntfIP": "10.254.0.1",
        "LeafAS": 65000,
        "Mask": "/31"
    }

    assert result[-1] == {
        "SU": 1,
        "SpineID": 3,
        "SpineName": "spine003",
        "SpineIntf": "swp128",
        "SpineIntfIP": "10.254.3.254",
        "SpineAS": 65203,
        "LeafID": 7,
        "LeafName": "leaf007",
        "LeafIntf": "swp128",    # 4 spines, each leaf has 16 connections to a spine. 4 x 16 total and starts from 65
        "LeafIntfIP": "10.254.3.255",
        "LeafAS": 65007,
        "Mask": "/31"
    }


def test_create_leaf_spine_port_mapping_64_hosts_non_air():
    mapper = NetworkMapping(num_hosts=64, nvidia_air=False)
    result = mapper.leaf_spine_mapping_data

    # total rows with 64 hosts, 8 leafs, 4 spines
    assert len(result) == 512   # 64 ports per leaf towards spine

    # Validate specific rows in the result2
    assert result[0] == {
        "SU": 0,
        "SpineID": 0,
        "SpineName": "spine000",
        "SpineIntf": "swp1s0",
        "SpineIntfIP": "10.254.0.0",
        "SpineAS": 65200,
        "LeafID": 0,
        "LeafName": "leaf000",
        "LeafIntf": "swp33s0",
        "LeafIntfIP": "10.254.0.1",
        "LeafAS": 65000,
        "Mask": "/31"
    }

    assert result[-1] == {
        "SU": 1,
        "SpineID": 3,
        "SpineName": "spine003",
        "SpineIntf": "swp64s1",
        "SpineIntfIP": "10.254.3.254",
        "SpineAS": 65203,
        "LeafID": 7,
        "LeafName": "leaf007",
        "LeafIntf": "swp64s1",    # 4 spines, each leaf has 16 connections to a spine. 4 x 16 total and starts from 65
        "LeafIntfIP": "10.254.3.255",
        "LeafAS": 65007,
        "Mask": "/31"
    }



def test_device_and_cable_count():
    mapper = NetworkMapping(96)

    assert mapper.num_spines == 8
    assert mapper.num_leafs == 12
    assert len(mapper.leaf_spine_mapping_data) == 768
    assert len(mapper.leaf_spine_mapping_data) + len(mapper.leaf_host_mapping_data) == 1536


def test_create_leaf_spine_port_mapping_1024_hosts():
    mapper = NetworkMapping(1024)
    result = mapper.leaf_spine_mapping_data

    # total rows with 1024 hosts, 128 leafs, 64 spines
    assert len(result) == 8192   # 64 ports per leaf towards spine, 64 * 128 = 8192

    assert result[-1] == {
        "SU": 31,
        "SpineID": 63,
        "SpineName": "spine063",
        "SpineIntf": "swp128",
        "SpineIntfIP": "10.254.63.254",
        "SpineAS": 65263,
        "LeafID": 127,
        "LeafName": "leaf127",
        "LeafIntf": "swp128",    # 4 spines, each leaf has 16 connections to a spine. 4 x 16 total and starts from 65
        "LeafIntfIP": "10.254.63.255",
        "LeafAS": 65127,
        "Mask": "/31"
    }


def test_create_leaf_host_p2p_data_air():
    mapper = NetworkMapping(32)
    result = mapper.host_dot_data
    print (result)
    assert len(result) == 256

    assert result[0] == {
        'SourceDevice': "leaf000",
        'SourceIntf': "swp1",
        'DstDevice': "dgx000",
        'DestIntf': "rail1"
    }

    assert result[1] == {
        'SourceDevice': "leaf000",
        'SourceIntf': "swp2",
        'DstDevice': "dgx000",
        'DestIntf': "rail2"
    }

    assert result[123] == {
        'SourceDevice': "leaf001",
        'SourceIntf': "swp32",
        'DstDevice': "dgx015",
        'DestIntf': "rail4"
    }


def test_create_leaf_spine_dot_data():
    mapper = NetworkMapping(128)    # 128 hosts = 4 SU = 16 Leafs = 8 Spines
    result = mapper.leaf_spine_dot_data

    assert len(result) == 1024

    assert result[-1] == {
        'SourceDevice': "leaf015",
        'SourceIntf': "swp128",
        'DstDevice': "spine007",
        'DestIntf': "swp128"
    }

    assert result[210] == {
        'SourceDevice': "leaf010",
        'SourceIntf': "swp75",
        'DstDevice': "spine001",
        'DestIntf': "swp83"
    }


def test_create_dot_graph_non_air():
    mapper = NetworkMapping(128, nvidia_air=False)
    dot_graph = mapper.create_dot_graph(write_to_file=False)

    dot_graph_entries = dot_graph.strip().split("\n")[1:-1]  # exclude the first and last line
    assert len(dot_graph_entries) == 2048  # account for connection between host to leaf and leaf to spine

    assert dot_graph_entries[0].strip() == '"leaf000":"swp1s0" -- "dgx000":"rail1"'
    assert dot_graph_entries[1023].strip() == '"leaf015":"swp32s1" -- "dgx127":"rail8"'
    assert dot_graph_entries[-1].strip() == '"leaf015":"swp64s1" -- "spine007":"swp64s1"'


def test_create_dot_graph_air():
    mapper = NetworkMapping(128)
    dot_graph = mapper.create_dot_graph(write_to_file=False)

    dot_graph_entries = dot_graph.strip().split("\n")[1:-1]  # exclude the first and last line
    assert len(dot_graph_entries) == 1048  # account for add'l entries for AIR

    assert (dot_graph_entries[0].strip() ==
            '"leaf000" [function="leaf" memory="2048" os="cumulus-vx-5.6.0" cpu="2" storage="10"]')
    assert (dot_graph_entries[20].strip() ==
            '"spine004" [function="spine" memory="2048" os="cumulus-vx-5.6.0" cpu="2" storage="10"]')
    assert (dot_graph_entries[-1].strip() ==
            '"leaf015":"swp128" -- "spine007":"swp128"')


def test_create_bgp_session_data():
    mapper = NetworkMapping(1024)
    result = mapper.bgp_session_data

    # 1024 * 8 = total number of hosts, then x 2 for 1 entry per side (1 on leaf and 1 on the spine)
    assert len(result) == 16384

    assert result[0] == {
        'DeviceName': "leaf000",
        'VRF': "default",
        'LocalAS': 65000,
        'NeighborIP': "10.254.0.0",
        'RemoteAS': 65200
    }

    assert result[8910] == {
        'DeviceName': "spine005",
        'VRF': "default",
        'LocalAS': 65205,
        'NeighborIP': "10.254.5.157",
        'RemoteAS': 65078
    }


def test_create_bgp_global_data():
    mapper = NetworkMapping(num_hosts=1024)
    result = mapper.bgp_global_data

    # 1024 * 8 = total number of hosts, then x 2 for 1 entry per side (1 on leaf and 1 on the spine)
    assert len(result) == 192

    assert result[0] == {
        "DeviceName": "leaf000",
        "VRF": "default",
        "AS": 65000,
        "LoopbackIP": ipaddress.IPv4Address("10.0.0.0"),
        "RouterID": ipaddress.IPv4Address("10.0.0.0")
    }

    assert result[100] == {
        "DeviceName": "leaf100",
        "VRF": "default",
        "AS": 65100,
        "LoopbackIP": ipaddress.IPv4Address("10.0.0.100"),
        "RouterID": ipaddress.IPv4Address("10.0.0.100")
    }

    assert result[191] == {
        "DeviceName": "spine063",
        "VRF": "default",
        "AS": 65263,
        "LoopbackIP": ipaddress.IPv4Address("10.1.0.63"),
        "RouterID": ipaddress.IPv4Address("10.1.0.63")
    }


def test_create_leaf_spine_interface_data():
    mapper = NetworkMapping(1024)
    result = mapper.leaf_spine_interface_data

    assert len(result) == 16384

    assert result[0] == {
        'DeviceName': "spine000",
        'Interface': "swp1",
        'InterfaceIP': "10.254.0.0",
        'Mask': "/31"
    }

    assert result[256] == {
        'DeviceName': "spine001",
        'Interface': "swp1",
        'InterfaceIP': "10.254.1.0",
        'Mask': "/31"
    }


with open("tests/test_data/netmapper_input_data.json") as f:
    netmapper_input_data = json.load(f)


def test_create_leaf_host_mapping_from_input():
    mapper = NetworkMapping(input_data=netmapper_input_data, num_spines=2)
    result = mapper.leaf_host_mapping_data
    assert len(result) == 8

    assert result[0] == {
        "SU": 1,
        "HostID": 1,
        "HostName": "hgx001",
        "Rail": 0,
        "HostIntf": "rail-0",
        "HostIntfIP": "172.0.1.2",      # 172.00000000.00000001.00000010
        "LeafID": 1,
        "LeafName": "leaf001",
        "LeafIntf": "swp1",
        "LeafIntfIP": "172.0.1.3",
        "Mask": "/31",
        "Description": "hgx001-rail-0"
    }

    assert result[7] == {
        "SU": 3,
        "HostID": 90,
        "HostName": "hgx090",
        "Rail": 2,
        "HostIntf": "rail-2",
        "HostIntfIP": "172.64.3.52",      # 172.01000000.00000011.00110100
        "LeafID": 11,
        "LeafName": "leaf011",
        "LeafIntf": "swp51",
        "LeafIntfIP": "172.64.3.53",
        "Mask": "/31",
        "Description": "hgx090-rail-2"
    }


def test_create_leaf_spine_mapping_from_input():
    mapper = NetworkMapping(input_data=netmapper_input_data, num_spines=2)
    result = mapper.leaf_spine_mapping_data
    assert len(result) == 8

    assert result[0] == {
        "SU": 1,
        "SpineID": 1,
        "SpineName": "spine001",
        "SpineIntf": "swp1",
        "SpineIntfIP": ipaddress.IPv4Address("10.254.1.0"),
        "SpineAS": 65201,
        "LeafID": 1,
        "LeafName": "leaf001",
        "LeafIntf": "swp65",
        "LeafIntfIP": ipaddress.IPv4Address("10.254.1.1"),
        "LeafAS": 65001,
        "Mask": "/31",
    }

    assert result[7] == {
        "SU": 2,
        "SpineID": 4,
        "SpineName": "spine004",
        "SpineIntf": "swp48",
        "SpineIntfIP": ipaddress.IPv4Address("10.254.4.94"),
        "SpineAS": 65204,
        "LeafID": 6,
        "LeafName": "leaf006",
        "LeafIntf": "swp96",
        "LeafIntfIP": ipaddress.IPv4Address("10.254.4.95"),
        "LeafAS": 65006,
        "Mask": "/31",
    }


def test_get_host_list():
    mapper = NetworkMapping(input_data=netmapper_input_data, num_spines=2)
    result = mapper._get_host_list()
    assert len(result) == 5

    assert result[0] == {
        'DeviceName': "hgx001",
        'Role': 'host'
    }


def test_get_device_list():
    mapper = NetworkMapping(input_data=netmapper_input_data, num_spines=2)
    result = mapper.devices
    assert len(result) == 9

    assert result[0] == {
        'DeviceName': "leaf001",
        'Role': 'leaf'
    }

    assert result[3] == {
        'DeviceName': "spine004",
        'Role': 'spine'
    }

    assert result[8] == {
        'DeviceName': "hgx090",
        'Role': 'host'
    }


@pytest.mark.parametrize(
    "num_hosts, expected_length",
    [
        (16, 128),     # 1 SU with 16 hosts will end up with 128 entries of IP assignment
        (32, 256),    # 1 SUs with 32 hosts will end up with 256 entries of IP assignment
        (176, 1408),     # 6 SUs with 176 hosts means 5 SUs with 32 hosts and 1 SU with 16 hosts.
        (4096, 32768)
    ]
)
def test_create_port_mapping_lengths(num_hosts, expected_length):
    mapper = NetworkMapping(num_hosts)
    result = mapper.leaf_host_mapping_data
    assert len(result) == expected_length
