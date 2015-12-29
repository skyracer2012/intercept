import os
import sys
import re

from xml.dom import minidom

def parse():
    scriptpath = os.path.realpath(__file__)
    projectpath = os.path.dirname(os.path.dirname(scriptpath))
    projectpath = os.path.join(projectpath, "src/client/intercept/client")
    projectpath_sqf = os.path.join(projectpath, "sqf")

    implementations = []
    declarations = []

    # Walk through our source files and figure out which ones are used in our code
    for file in os.listdir(projectpath_sqf):
        foundInFile = 0
        if file.endswith(".cpp") or file.endswith(".hpp"):
            source_file = os.path.join(projectpath_sqf, file)
            lineN = 0
            with open(source_file) as f:
                filecontents = re.sub("(/\*[.\s\w\W]*?\*/)", '', f.read())
                filecontents = re.sub("(//.*?\n)", '', filecontents)

                if file.endswith(".cpp"):
                    match_impls = re.findall("([a-zA-Z0-9:_<>]+,*?\s*[a-zA-Z0-9:_<>]+>|[a-zA-Z0-9:_<>]+)\s+([a-zA-Z0-9_]+)(\(.*?\))(?=\s*\{)", filecontents)
                    for match_impl in match_impls:
                        if (match_impl):
                            foundInFile += 1
                            if (match_impl[1].startswith("__")):
                                continue
                            implementations.append([match_impl[0], match_impl[1], match_impl[2], [file, lineN]]) # full contract of our implementation
                if file.endswith(".hpp"):
                    match_impls = re.findall("([a-zA-Z0-9:_<>]+,*?\s*[a-zA-Z0-9:_<>]+>|[a-zA-Z0-9:_<>]+)\s+([a-zA-Z0-9_]+)(\(.*?\))(?=\s*\;)", filecontents)
                    for match_impl in match_impls:
                        if (match_impl):
                            foundInFile += 1
                            if (match_impl[1].startswith("__")):
                                continue
                            declarations.append([match_impl[0], match_impl[1], match_impl[2], [file, lineN]]) # full contract of our declaration

    errors_found = []
    warnings_found = []

    parsed_impl = []
    # strip default values
    for impl in implementations:
        impl[2] = re.sub("(\s*=\s*[a-zA-Z0-9\"]+)(?=[,\)])", r"", impl[2]).lower()
        elements = impl[2].split(',')
        if (impl[2] == "()"):
            parsed_impl.append(impl)
            continue
        impl[2] = ''
        to_add = False
        for el in elements:
            # element_type = re.search("(const\s+[a-zA-Z0-9:<>_]+\s*[&\*]*|[a-zA-Z0-9:<>_]+\s*[&\*]*)[a-zA-Z0-9]*", el)
            el = re.sub("(\*|&)", r" \1 ", el)
            element_type = re.search("(const\s+[a-zA-Z0-9:<>_]+\s*[&\*]?|[a-zA-Z0-9:<>_]+\s*[&\*]?)\s+[a-zA-Z_]*?", el)
            if (element_type):
                element_type = element_type.group(1)
                impl[2] += element_type + ', '
                to_add = True
        impl[2] = "(" + impl[2] + ")"
        impl[2] = re.sub(", \)", ')', impl[2])
        impl[2] = re.sub("\s+(\&|\*)", r'\1', impl[2])
        if to_add:
            parsed_impl.append(impl)

    implementations = parsed_impl
    parsed_impl = []
    # Check for default values in declarations
    for decl in declarations:
        match = re.search("(\s*=\s*[a-zA-Z0-9\"]+)(?=[,\)])", decl[2])
        if (match):
            warnings_found.append("Found a default value in declaration parameters ({}, {} line {})".format(decl[1], decl[3][0], decl[3][1]))
            decl[2] = re.sub("(\s*=\s*[a-zA-Z0-9\"]+)(?=[,\)])", r"", decl[2]).lower() # get rid of them here, so we can continue checking for errors

        # split up using , seperators
        # for each element, find type and remove parameter name
        # combine all elements, we now got our function contract
        elements = decl[2].split(',')
        if (decl[2] == "()"):
            parsed_impl.append(decl)
            continue
        decl[2] = ''
        to_add = False
        for el in elements:
            # element_type = re.search("(const\s+[a-zA-Z0-9:<>_]+\s*[&\*]*|[a-zA-Z0-9:<>_]+\s*[&\*]*)[a-zA-Z0-9]*", el)
            el = re.sub("(\*|&)", r" \1 ", el)
            element_type = re.search("(const\s+[a-zA-Z0-9:<>_]+\s*[&\*]?|[a-zA-Z0-9:<>_]+\s*[&\*]?)\s+[a-zA-Z_]*?", el)
            if (element_type):
                element_type = element_type.group(1)
                decl[2] += element_type + ', '
                to_add = True
        decl[2] = "(" + decl[2] + ")"
        decl[2] = re.sub(", \)", ')', decl[2])
        decl[2] = re.sub("\s+(\&|\*)", r'\1', decl[2])
        if to_add:
            parsed_impl.append(decl)
    declarations = parsed_impl

    ##### START VALIDATION #####

    # Check for implementations without declarations
    for impl in implementations:
        found = False
        for decl in declarations:
            if (impl[1] == decl[1] and impl[2] == decl[2] and impl[0] == decl[0]):
                found = True
                break
        if (not found):
            errors_found.append("Missing declaration for implementation {} {}{} [{}]".format(impl[0], impl[1], impl[2], impl[3][0]))

    # Check for duplicate implementations
    for impl in implementations:
        duplicate_counter = 0
        for impl_comp in implementations: # check everything against each other. Yay, go brute force
            if (impl[1] == impl_comp[1]): # ignoring return value, since we can only overload parameters. If name and parameters match, we got a duplicate.
                if impl[2] == impl_comp[2]:
                    duplicate_counter+=1
                    if (impl[0] != impl_comp[0]): # this is invalid, cannot overload return values
                        errors_found.append("Return value in function contract mismatch. Expected: {}. Found: {} at {} in {}, line {}\n".format(impl[0], impl_comp[0], impl_comp[1], impl_comp[3][0], impl_comp[3][1]))

                if duplicate_counter > 1:
                    errors_found.append("Found a duplicate implementation for {} in {}, line {}\n".format(impl_comp[1], impl_comp[3][0], impl_comp[3][1]))

    # Check for declarations without implementation
    for decl in declarations:
        found = False
        for impl in implementations:
            if (impl[1] == decl[1] and impl[2] == decl[2] and impl[0] == decl[0]):
                found = True
                break

        if (not found):
            errors_found.append("Missing implementation for declaration {} {}{} [{}]".format(decl[0], decl[1], decl[2], decl[3][0]))

    for warning in warnings_found:
        print("WARNING: " +warning)
    for error in errors_found:
        print("ERROR: "+ error)

    print("\n\n-------\nWarnings: {} Errors: {}".format(len(warnings_found), len(errors_found)))
    print("Total implementations {0} | Total Declarations {1}".format(len(implementations), len(declarations)))

    if (len(errors_found) > 0):
        print("FAILED")
        return 1
    else:
        print("PASSED")
        return 0

if __name__ == "__main__":
    sys.exit(parse())
