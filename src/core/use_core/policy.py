# VERITAS: Copyright (c) 2022 Veritas Technologies LLC. All rights reserved.
#
# THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF VERITAS
# TECHNOLOGIES LLC.  USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE
# PRIOR EXPRESS WRITTEN PERMISSION OF VERITAS TECHNOLOGIES LLC.
#
# The Licensed Software and Documentation are deemed to be commercial computer
# software as defined in FAR 12.212 and subject to restricted rights as defined
# in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights"
# and DFARS 227.7202, Rights in "Commercial Computer Software or Commercial
# Computer Software Documentation," as applicable, and any successor
# regulations, whether delivered by Veritas as on premises or hosted services.
# Any use, modification, reproduction release, performance, display or
# disclosure of the Licensed Software and Documentation by the U.S. Government
# shall be solely in accordance with the terms of this Agreement.
# Product version __version__

"""
The Policy classes that allow Excel cells to be filled in with
validation parameters.
"""


class NoPolicy:
    def policy(self):
        return {"validate": "any"}


class NamePolicy:
    def __init__(self, maybe_empty=False):
        self.maybe_empty = maybe_empty

    def policy(self):
        rule = {
            "validate": "length",
            "criteria": ">",
            "value": 1,
            "ignore_blank": False,
        }
        if self.maybe_empty:
            rule["ignore_blank"] = True
        return rule


class NumberPolicy:
    def __init__(self, minimum, maximum=None, message=None):
        self.minimum = minimum
        self.maximum = maximum
        self.message = message

    def policy(self):
        pol = {"validate": "integer", "minimum": self.minimum}
        if self.maximum is None:
            pol["criteria"] = ">="
        else:
            pol["criteria"] = "between"
            pol["maximum"] = self.maximum

        if self.message is not None:
            pol["input_message"] = self.message

        return pol


class NumberPolicyNoUpperBound(NumberPolicy):
    """
    Like NumberPolicy but minimum defaults to zero and there is no
    upper limit.
    """

    def __init__(self, minimum=0, **kwargs):
        super().__init__(minimum, **kwargs)


class DecimalPolicy:
    def __init__(self, minimum, maximum=1.0):
        self.minimum = minimum
        self.maximum = maximum

    def policy(self):
        if self.maximum is not None:
            return {
                "validate": "decimal",
                "criteria": "between",
                "minimum": self.minimum,
                "maximum": self.maximum,
            }
        else:
            return {"validate": "decimal", "criteria": ">=", "value": self.minimum}


class DecimalPolicyNoUpperBound(DecimalPolicy):
    def __init__(self, minimum):
        super().__init__(minimum, None)


class ChoicePolicy:
    def __init__(self, choices):
        self.choices = choices

    def policy(self):
        return {"validate": "list", "source": self.choices}


class CustomPolicy:
    def __init__(self, validation_formula):
        self.formula = validation_formula

    def policy(self):
        return {"validate": "custom", "value": self.formula}
