from copy import deepcopy
import json
import csv

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from f90nml.namelist import Namelist


class NamelistDiff():
    # TODO document
    def __init__(self, input_nml, label):
        self.unique = OrderedDict()
        self.equal = OrderedDict()
        self.different = OrderedDict()
        # Labels holder
        self._labels = [label]
        # Other attributes used for the methods
        # Just to avpid passing the each time to the methods
        self._isdiff = None

        if not isinstance(label, str):
            # TODO write error message
            raise TypeError

        if isinstance(input_nml, Namelist):
            input_nml = input_nml.todict()
        elif not isinstance(input_nml, dict):
            # TODO write error message
            raise TypeError

        # Copy input to avoid mutating the original object in the future
        self.unique[label] = input_nml.copy()

    def __str__(self):
        out = "NamelistDiff object\n"
        out += "\nUnique values:\n"
        out += self._dump(self.unique)
        out += "\nEqual values:\n"
        out += self._dump(self.equal)
        out += "\nDifferent values:\n"
        out += self._dump(self.different)
        return out

    def _dump(self, section):
        out = ""
        for key in section:
            out += "  "+" ".join(key) + "\n    "
            out += json.dumps(
                section[key], sort_keys=True, indent=2
            ).replace("\n", "\n    ")
        return out

    def copy(self):
        """Copy the object."""
        return deepcopy(self)

    def diff(self, new_input, new_label, inplace=False):
        """
        Compute the difference of current object with a new namelist.

        Parameters
        ----------
        new_input: str or pathlib.Path or f90nml.namelist.Namelist or dict
            New input data. If str or pathlib.Path it will be read from
            a file. Otherwise, the input object information will be used.
        new_label: str
            Label for the new input data. It is recommended to use a
            "safe" name with no whitespaces or special characters.
        inplace: bool (optional)
            If True it will modify the current object. Otherwise, it will
            return a new object with the method result. Default is False.

        """
        if new_label in self._labels:
            # TODO write error message
            raise ValueError
        if not isinstance(new_label, str):
            # TODO write error message
            raise TypeError
        if isinstance(new_input, Namelist):
            new_input = new_input.todict()
        if not isinstance(new_input, dict):
            # TODO write error message
            raise TypeError

        if inplace:
            # Mutates current object
            self._diff(new_input.copy(), new_label)
            return None
        else:
            # Creates a copy for the difference
            new_diff = self.copy()
            new_diff._diff(new_input.copy(), new_label)
            return new_diff

    def _diff(self, input, label):
        """Method for computing the differences"""
        # Compare existing unique dicts
        for key, values in self.unique.copy().items():
            self._isdiff = False
            self._compare_dicts(values, input, [(key, label)])
        # Compare existing equal dicts
        for key, values in self.equal.copy().items():
            self._isdiff = False
            self._compare_dicts(values, input, [(*key, label)])
        # Compare existing different dicts
        for key, values in self.different.copy().items():
            self._isdiff = True
            self._compare_dicts(values, input, [(*key, label)])

        # Writte the value still hold in input (unique)
        if input:
            self.unique[label] = input.copy()

        # Remove those sections that are empty
        for section in ("unique", "equal", "different"):
            sec = getattr(self, section)
            keys = [key for key in sec if not sec[key]]
            for key in keys:
                del sec[key]

        # Reset to None arguments
        self._isdiff = None

    def _compare_dicts(self, self_nml, in_nml, path):
        """
        Compare the keys and values between two dictionaries and update
        a NamelistDiff object
        """
        for key in set(self_nml).intersection(in_nml):
            new_path = path + [key]
            if isinstance(self_nml[key], dict):
                # keep entering a nested level
                self._compare_dicts(self_nml[key], in_nml[key], new_path)
                # Delete groups from previous dictionaries if they are
                # empty after checking their values
                if not self_nml[key]:
                    del self_nml[key]
                if not in_nml[key]:
                    del in_nml[key]
            else:
                # compare values
                self._compare_values(self_nml[key], in_nml[key], new_path)
                # Delete value from previous dictionaries
                del self_nml[key], in_nml[key]

    def _compare_values(self, self_val, ref_val, path):
        """Compare two values from a namelist"""
        if self._isdiff:
            # It is already a different values dictionary, no need to
            # compare the values
            self._update_dict(self.different, path, self_val + [ref_val])
        elif self_val == ref_val:
            # Elements are equal
            self._update_dict(self.equal, path, self_val)
        else:
            # First n-1 values are equal and last one different
            self._update_dict(
                self.different, path,
                (len(path[0])-1)*[self_val] + [ref_val]
            )

    def _update_dict(self, section, path, value):
        """Update dictionary addying new entries if needed"""
        cdict = section
        # Iterate over the path in the dictionary
        for key in path[:-1]:
            if key not in cdict:
                # Create key if neccessary
                cdict[key] = {}
            cdict = cdict[key]
        # Assign the new value
        cdict[path[-1]] = value

    def to_csv(self, out, extension=".csv", **fmtparams):
        """
        Save the difference information in an spreadsheet file

        Parameters
        ----------
        out: str or pathlib.Path
            Name of the output file to save
        extension: str (optional)
        **fmtparams:
            csv.writter **fmtparams keyword arguments.

        """
        # Write each table to a different file.
        summary = []
        for i, key in enumerate(self.unique):
            file_name = 'unique_' + str(i) + extension
            summary.append([file_name, "Unique values in '%s'" % key])
            head, out = self._convert_to_lists(self.unique[key], (key,))
            with open(file_name, 'w') as csvfile:
                spamwriter = csv.writer(csvfile, **fmtparams)
                spamwriter.writerow(head)
                for out_i in out:
                    spamwriter.writerow(out_i)
        for i, key in enumerate(self.equal):
            file_name = 'equal_' + str(i) + extension
            keys = " ".join(["'%s'" % val for val in key])
            summary.append([file_name, "Equal values between %s" % keys])
            head, out = self._convert_to_lists(self.equal[key], (keys,))
            with open(file_name, 'w') as csvfile:
                spamwriter = csv.writer(csvfile, **fmtparams)
                spamwriter.writerow(head)
                for out_i in out:
                    spamwriter.writerow(out_i)
        for i, key in enumerate(self.different):
            file_name = 'diff_' + str(i) + extension
            keys = " ".join(["'%s'" % val for val in key])
            summary.append([file_name, "Different values between %s" % keys])
            head, out = self._convert_to_lists(self.different[key], key)
            with open(file_name, 'w') as csvfile:
                spamwriter = csv.writer(csvfile, **fmtparams)
                spamwriter.writerow(head)
                for out_i in out:
                    spamwriter.writerow(out_i)

        # Write summary sheet
        file_name = 'summary' + extension
        with open(file_name, 'w') as csvfile:
            spamwriter = csv.writer(csvfile, **fmtparams)
            spamwriter.writerow(['Sheet', 'Description'])
            for out_i in summary:
                spamwriter.writerow(out_i)

    @staticmethod
    def _convert_to_lists(indict, varcols):
        """Convert a dictionary to a list of lists"""
        n_varcols = len(varcols)
        out = NamelistDiff._to_lists(indict, n_varcols)
        # Convert all the list to the same length by prepending Nones
        out_n = max([len(out_i) for out_i in out])
        out = [[None]*(out_n-len(out_i))+out_i for out_i in out]
        head = [
            "level "+str(i) for i in range(len(out[0])-n_varcols)
            ] + list(varcols)
        return head, out

    @staticmethod
    def _to_lists(indict, n_values):
        """Search along dictionary to create each row list"""
        if isinstance(indict, dict):
            # continue searching
            outs = []
            for key, values in indict.items():
                out = NamelistDiff._to_lists(values, n_values)
                outs += [[key] + val for val in out]
            return outs
        elif n_values == 1:
            # unique and equal sections have only one value (create a list)
            return [[indict]]
        else:
            # difference section has more than one value (already a list)
            return [indict]