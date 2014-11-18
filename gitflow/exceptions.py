#
# This file is part of `gitflow`.
# Copyright (c) 2010-2011 Vincent Driessen
# Copyright (c) 2012 Hartmut Goebel
# Distributed under a BSD-like license. For full terms see the file LICENSE.txt
#

__copyright__ = "2010-2011 Vincent Driessen; 2012 Hartmut Goebel"
__license__ = "BSD"

class GitflowError(Exception): pass

class Usage(GitflowError):
    def __str__(self):
        return '\n'.join(map(str, self.args))

class OperationsError(GitflowError): pass
class PrefixNotUniqueError(OperationsError): pass
class MergeError(OperationsError): pass
class PostReviewError(OperationsError): pass
class SubmitReviewError(OperationsError): pass

class StatusError(GitflowError): pass
class WorkdirIsDirtyError(StatusError): pass
class NotInitialized(StatusError): pass
class AlreadyInitialized(StatusError):
    def __str__(self):
        return ("Already initialized for gitflow.\n"
                "To force reinitialization use: git flow init -f")
class MultipleReviewRequestsForBranch(StatusError):
    def __str__(self):
        return 'Multiple review requests for {0} were found'.format(self.args[0])
class IllegalCommunicationProtocol(StatusError): pass
class RemoteNotFound(StatusError): pass

class MergeConflict(StatusError):
    def __str__(self):
        return '\n'.join([
            "Merge conflicts not resolved yet, use:",
            "    git mergetool",
            "    git commit",
            ])

class StoryError(StatusError): pass
class ReleaseAlreadyAssigned(StoryError): pass
class PointMeError(StoryError): pass

class EmptyDiff(StatusError): pass

class InconsistencyDetected(StatusError):
    def __str__(self):
        return "Inconsistency detected: {0}".format(self.args[0])

class ObjectError(GitflowError): pass
class BadObjectError(ObjectError): pass
class NoSuchBranchError(ObjectError): pass
class NoSuchRemoteError(ObjectError): pass

class BaseNotOnBranch(ObjectError):
    def __str__(self):
        return ("Branch '%s' found in the repository," \
                "but it is diverging from '%s'" \
                % (self.args[1], self.args[0]))

class BaseNotFound(ObjectError): pass
class BaseNotAllowed(ObjectError): pass

class AncestorNotFound(ObjectError): pass

class BranchExistsError(ObjectError):pass
class TagExistsError(ObjectError): pass

class BranchTypeExistsError(ObjectError):
    def __str__(self):
        return("There is an existing %s branch. "
                "Finish that one first." % self.args[0])

class NoSuchLocalBranchError(NoSuchBranchError):
    def __str__(self):
        return ("Local branch '%s' does not exist." % self.args[0])


class IllegalVersionFormat(GitflowError):
    def __str__(self):
        return "Version string is ill-formed, it is not matching " + \
                self.args[0]
