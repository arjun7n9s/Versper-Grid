import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/arjun7n9s/Downloads/AMD-S-2/ros2_temp/install/evidence_bridge'
