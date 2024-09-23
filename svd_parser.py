import xml.etree.ElementTree as ET
from typing import *

tree: ET.ElementTree = ET.parse('CM0plus.svd')
root: ET.Element = tree.getroot()

def list_registers() -> None:
    # Peripheral
    for peripheral in root.findall(".//peripheral"):
        peripheral_name: str = peripheral.find('name').text
        peripheral_base_address: str = peripheral.find('baseAddress').text
        print(f'// {peripheral_name}')
        print(f'// {"=" * len(peripheral_name)}')

        # Check for 'derivedFrom' attribute
        derived_from: Optional[str] = peripheral.get('derivedFrom')
        if derived_from:
            print(f"// {peripheral_name} is derived from {derived_from}")
            original_peripheral = root.find(f".//peripheral[name='{derived_from}']")
            peripheral = original_peripheral

        # Register
        for register in peripheral.findall(".//register"):
            print(
                extract_typedef(register, peripheral_name, peripheral_base_address)
            )
            print('')
            continue
        print('')

        continue
    return

def get_register_type(size: int) -> str:
    if size == 8:
        return 'uint8_t'
    elif size == 16:
        return 'uint16_t'
    elif size == 32:
        return 'uint32_t'
    elif size == 64:
        return 'uint64_t'
    return f'uint{size}_t'  # For other sizes

def extract_typedef(register: ET.Element,
                    peripheral_name: str,
                    peripheral_base_address: str,
                    ) -> str:
    '''
    Extract the typedef for the register, as well as the #define macros.
    '''
    typedef_str_list: List[str] = []

    register_name: str = register.find('name').text

    # The function now checks for the <dim> element to determine if the register is an array.  If
    # the register is an array, it calculates the base address and treats the register as an array
    # of volatile pointers. It also generates appropriate macros to access the array elements. A
    # helper function `get_register_type` is added to determine the correct C data type (uint8_t,
    # uint16_t, uint32_t, etc.) based on the size specified in the SVD file.

    # Handle 'dim' attribute
    dim_element = register.find('dim')
    if dim_element is not None:
        # Register is an array
        dim = int(dim_element.text)
        dim_increment = int(register.find('dimIncrement').text, 0)
        dim_index = register.find('dimIndex').text

        register_size = int(register.find('size').text)
        register_type = get_register_type(register_size)

        register_address_offset = int(register.find('addressOffset').text, 16)
        register_address = int(peripheral_base_address, 16) + register_address_offset

        # Generate the typedef for the bits of a single element
        typedef_str_list.append(f'typedef struct __attribute__((__packed__)) {{')

        field_dict: Dict[str, Tuple[int, int]] = {}
        for field in register.findall(".//field"):
            field_name: str = field.find('name').text
            field_bit_offset: str = field.find('bitOffset').text
            field_bit_width: str = field.find('bitWidth').text
            field_start_bit: int = int(field_bit_offset)
            field_end_bit: int = field_start_bit + int(field_bit_width) - 1
            field_dict[field_name] = (field_start_bit, field_end_bit)

        # Build struct for a single element
        field_dict = dict(sorted(field_dict.items(), key=lambda x: x[1][0]))
        last_end_bit: int = -1
        total_bits = register_size
        for field_name, (field_start_bit, field_end_bit) in field_dict.items():
            if last_end_bit + 1 != field_start_bit:
                # Add reserved bits
                typedef_str_list.append(f'    {register_type} : {field_start_bit - last_end_bit -1};')
            typedef_str_list.append(f'    {register_type} {field_name}: {field_end_bit - field_start_bit + 1};')
            last_end_bit = field_end_bit
        if last_end_bit < total_bits -1:
            typedef_str_list.append(f'    {register_type} : {total_bits - last_end_bit -1};')
        typedef_str_list.append(f'}} {peripheral_name}_{register_name}bits_t;')

        # Now define the array macros
        typedef_str_list.append(f'#define {peripheral_name}_{register_name} ((volatile {register_type} *){hex(register_address)})')
        typedef_str_list.append(f'#define {peripheral_name}_{register_name}bits ((volatile {peripheral_name}_{register_name}bits_t *){hex(register_address)})')

    else:
        # Register is not an array
        try:
            register_size = int(register.find('size').text)
        except ValueError:
            register_size = int(register.find('size').text, 16)
        register_type = get_register_type(register_size)

        register_address = hex(
            int(peripheral_base_address, 16) + int(register.find('addressOffset').text, 16)
        )

        typedef_str_list.append(f'typedef struct __attribute__((__packed__)) {{')

        field_dict: Dict[str, Tuple[int, int]] = {}
        for field in register.findall(".//field"):
            field_name: str = field.find('name').text
            field_bit_offset: str = field.find('bitOffset').text
            field_bit_width: str = field.find('bitWidth').text
            field_start_bit: int = int(field_bit_offset)
            field_end_bit: int = field_start_bit + int(field_bit_width) - 1
            field_dict[field_name] = (field_start_bit, field_end_bit)

        # Insert RESERVED fields for all the gaps
        field_dict = dict(sorted(field_dict.items(), key=lambda x: x[1][0]))
        last_end_bit: int = -1
        total_bits = register_size
        for field_name, (field_start_bit, field_end_bit) in field_dict.items():
            if last_end_bit + 1 != field_start_bit:
                typedef_str_list.append(f'    {register_type} : {field_start_bit - last_end_bit - 1};')
            typedef_str_list.append(f'    {register_type} {field_name}{" "*(5-len(field_name))}: {field_end_bit - field_start_bit + 1};')
            last_end_bit = field_end_bit
            continue
        if last_end_bit < total_bits -1:
            typedef_str_list.append(f'    {register_type} : {total_bits - last_end_bit -1};')
        typedef_str_list.append(f'}} {peripheral_name}_{register_name}bits_t;')

        typedef_str_list.append(f'#define {peripheral_name}_{register_name} (*(volatile {register_type} *){register_address})')
        typedef_str_list.append(f'#define {peripheral_name}_{register_name}bits (*(volatile {peripheral_name}_{register_name}bits_t *){register_address})')

    return '\n'.join(typedef_str_list)

if __name__ == '__main__':
    list_registers()

# REFACTORING THE CODE TO HANDLE REGISTER ARRAYS
# ==============================================
# Before the latest change, where the code was refactored to handle register arrays, the output for
# the NVIC_IP register from the Cortex-M0+ was as follows:
#
#     typedef struct __attribute__((__packed__)) {
#         uint32_t : 32;
#     } NVIC_IPbits_t;
#     #define NVIC_IP (*(volatile uint32_t *)0xe000e400)
#     #define NVIC_IPbits (*(volatile NVIC_IPbits_t *)0xe000e400)
#
# Notice that NVIC_IP is dereferenced here. So you can write something directly to the register.
#
# After the change, the output for the NVIC_IP register is as follows:
#
#     typedef struct __attribute__((__packed__)) {
#         uint8_t : 8;
#     } NVIC_IPbits_t;
#     #define NVIC_IP ((volatile uint8_t *)0xe000e400)
#     #define NVIC_IPbits ((volatile NVIC_IPbits_t *)0xe000e400)
#
# Notice that NVIC_IP is not dereferenced here. So you first need to dereference it before writing
# something. However, that's exactly what we need, because that's what the array syntax does for us.
# Remember:
#     x[n] == *(x + n)
#
# So:
#     NVIC_IP[0] == *(NVIC_IP + 0)
#     NVIC_IP[1] == *(NVIC_IP + 1)
#     ...
#
# 
#
# The NVIC_IP register had no fields. Its SVD snippet was:
#
#     <register>
#         <name>IP</name>
#         <description>Interrupt Priority Register</description>
#         <addressOffset>0x300</addressOffset>
#         <size>8</size>
#         <access>read-write</access>
#         <dim>32</dim>
#         <dimIncrement>0x1</dimIncrement>
#         <dimIndex>0-31</dimIndex>
#     </register>
#
# After an SVD update, it now has fields:
#
#     <register>
#         <name>IP</name>
#         <description>Interrupt Priority Register</description>
#         <addressOffset>0x300</addressOffset>
#         <size>8</size>
#         <access>read-write</access>
#         <dim>32</dim>
#         <dimIncrement>0x1</dimIncrement>
#         <dimIndex>0-31</dimIndex>
#         <fields>
#             <field>
#                 <name>RESERVED</name>
#                 <description>Reserved</description>
#                 <bitOffset>0</bitOffset>
#                 <bitWidth>6</bitWidth>
#             </field>
#             <field>
#                 <name>PRI</name>
#                 <description>Priority Bits</description>
#                 <bitOffset>6</bitOffset>
#                 <bitWidth>2</bitWidth>
#             </field>
#         </fields>
#     </register>
# 
# The output for this is:
#
#     typedef struct __attribute__((__packed__)) {
#         uint8_t RESERVED: 6;
#         uint8_t PRI: 2;
#     } NVIC_IPbits_t;
#     #define NVIC_IP ((volatile uint8_t *)0xe000e400)
#     #define NVIC_IPbits ((volatile NVIC_IPbits_t *)0xe000e400)
#
# Again, notice that the NVIC_IP is not dereferenced. You can use the array syntax to do that:
#
#     NVIC_IPbits[9].PRI = 0b10;
# Or:
#     NVIC_IPbits_t ip_bits;
#     ip_bits.PRI = 0b10;
#     NVIC_IPbits[9] = ip_bits;
