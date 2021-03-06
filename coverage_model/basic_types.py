#!/usr/bin/env python

"""
@package coverage_model.basic_types
@file coverage_model/basic_types.py
@author Christopher Mueller
@brief Base classes for Coverage Model and Parameter classes
"""

from ooi.logging import log
import numpy as np
import uuid

def create_guid():
    """
    @retval Return global unique id string
    """
    # guids seem to be more readable if they are UPPERCASE
    return str(uuid.uuid4()).upper()

class Dictable(object):

    def dump(self):
        """
        Retrieve a standard python dict representing the Dictable object and any Dictable sub-objects.

        Delegates to self._todict()

        @returns    A python dictionary representation of the object
        """
        return self._todict()

    @classmethod
    def load(cls, fromdict):
        """
        Create an object of type cls from a properly formed dict (i.e. one created from cls.dump)

        Delegates to cls._fromdict()

        @param cls  An object inheriting from Dictable
        @param fromdict    A python dict representation of a valid Dictable; may contain other Dictable objects
        """
        return cls._fromdict(fromdict)

    def _todict(self):
        """
        Retrieve a standard python dict representing the Dictable object and any Dictable sub-objects.

        This function may be overridden in subclasses to handle special functionality

        @returns    A python dictionary representation of the object
        """
        ret = dict((k,v._todict() if hasattr(v, '_todict') else v) for k, v in self.__dict__.iteritems())

        ret['cm_type'] = (self.__module__, self.__class__.__name__)
        return ret

    @classmethod
    def _fromdict(cls, cmdict, arg_masks=None):
        """
        Create an object of type cls from a properly formed dict (i.e. one created from cls._todict)

        This function may be overridden in subclasses to handle special functionality

        MASKING:
            To provide for required constructor arguments that are different name from the corresponding attribute
            within the object, a dict of str:str members may be provided where the key is the name of the constructor
            argument and the value is the corresponding class attribute
            See SimplexCoverage.__init__ and SimplexCoverage._fromdict for an example

        @param cls  An object inheriting from Dictable
        @param cmdict    A python dict representation of a valid Dictable; may contain other Dictable objects
        @param arg_masks    Allows masking of required constructor arguments - see MASKING above
        """
        arg_masks = arg_masks or {}
        log.debug('_fromdict: cls=%s',cls)
        if isinstance(cmdict, dict) and 'cm_type' in cmdict and cmdict['cm_type']:
            cmd = cmdict.copy()
            import inspect
            mod = inspect.getmodule(cls)
            ptmod_s, ptcls_s=cmd.pop('cm_type')
            ptcls=getattr(mod, ptcls_s)

            # Get the argument specification for the initializer
            spec = inspect.getargspec(ptcls.__init__)
            args = spec.args[1:] # get rid of 'self'
            # Remove any optional arguments
            if spec.defaults: # if None, all are required
                for i in spec.defaults:
                    args.remove(args[-1])
            kwa={}
            for a in args:
                # Apply any argument masking
                am = arg_masks[a] if a in arg_masks else a
                if am in cmd:
                    val = cmd.pop(am)
                    if isinstance(val, dict) and 'cm_type' in val:
                        ms, cs = val['cm_type']
                        module = __import__(ms, fromlist=[cs])
                        classobj = getattr(module, cs)
                        kwa[a] = classobj._fromdict(val)
                    else:
                        kwa[a] = val
                else:
                    kwa[a] = None

            ret = ptcls(**kwa)
            for k,v in cmd.iteritems():
                if isinstance(v, dict) and 'cm_type' in v:
                    ms, cs = v['cm_type']
                    module = __import__(ms, fromlist=[cs])
                    classobj = getattr(module, cs)
                    setattr(ret,k,classobj._fromdict(v))
                else:
                    setattr(ret,k,v)


            return ret
        else:
            raise TypeError('cmdict is not properly formed, must be of type dict and contain a \'cm_type\' key: {0}'.format(cmdict))

class AbstractBase(Dictable):
    """
    Base class for all coverage model objects

    Provides id, mutability and extension attributes
    """
    def __init__(self, id=None, mutable=None, extension=None):
        """
        Construct a new AbstractBase object

        @param id   The ID of this object type
        @param mutable  The mutability of the object; defaults to False
        """
        self._id = id
        self.mutable = mutable or False
        self.extension = extension or {}

    @property
    def id(self):
        return self._id

class AbstractIdentifiable(AbstractBase):
    """
    Base identifiable class for all coverage model objects

    Provides identifier, label and description attributes
    """
    def __init__(self, identifier=None, label=None, description=None, **kwargs):
        """
        Construct a new AbstractIdentifiable object

        @param identifier   The UUID of this 'instance'
        @param label    The short description of the object
        @param description  The full description of the object
        @param **kwargs Additional keyword arguments are copied and the copy is passed up to AbstractBase; see documentation for that class for details
        """
        kwc=kwargs.copy()
        AbstractBase.__init__(self, **kwc)
        # TODO: Need to decide if identifier is assigned on creation or on demand (when asked for); using the latter for the time being
        self._identifier = identifier
        self.label = label or ''
        self.description = description or ''

    @property
    def identifier(self):
        """
        The UUID of the object.  Generated on first request.
        """
        if self._identifier is None:
            self._identifier = create_guid()

        return self._identifier

class AbstractStorage(AbstractBase):

    def __init__(self, dtype=None, fill_value=None, **kwargs):
        """

        @param **kwargs Additional keyword arguments are copied and the copy is passed up to AbstractBase; see documentation for that class for details
        """
        kwc=kwargs.copy()
        AbstractBase.__init__(self, **kwargs)
        self.dtype = dtype or '|O8'
        self.fill_value = fill_value

    def __getitem__(self, slice_):
        raise NotImplementedError('Not implemented in abstract class')

    def __setitem__(self, slice_, value):
        raise NotImplementedError('Not implemented in abstract class')

    def expand(self, arrshp, origin, expansion):
        raise NotImplementedError('Not implemented in abstract class')

    def fill(self, value):
        raise NotImplementedError('Not implemented in abstract class')

    def __len__(self):
        raise NotImplementedError('Not implemented in abstract class')

    def __iter__(self):
        raise NotImplementedError('Not implemented in abstract class')

class InMemoryStorage(AbstractStorage):

    def __init__(self, dtype=None, fill_value=None, **kwargs):
        """

        @param **kwargs Additional keyword arguments are copied and the copy is passed up to AbstractStorage; see documentation for that class for details
        """
        kwc=kwargs.copy()
        AbstractStorage.__init__(self, dtype=dtype, fill_value=fill_value, **kwc)
        self._storage = np.empty((0,), dtype=self.dtype)

    def __getitem__(self, slice_):
        return self._storage.__getitem__(slice_)

    def __setitem__(self, slice_, value):
        self._storage.__setitem__(slice_, value)

    def expand(self, arrshp, origin, expansion):
        narr = np.empty(arrshp, dtype=self.dtype)
        narr.fill(self.fill_value)
        loc=[origin for x in xrange(expansion)]
        self._storage = np.insert(self._storage[:], loc, narr, axis=0)

    def fill(self, value):
        self._storage.fill(value)

    def __len__(self):
        return self._storage.__len__()

    def __iter__(self):
        return self._storage.__iter__()

class DomainOfApplication(object):
    # CBM: Document this!!
    def __init__(self, slices, topoDim=None):
        if slices is None:
            raise StandardError('\'slices\' cannot be None')
        self.topoDim = topoDim or 0

        if is_valid_constraint(slices):
            if not np.iterable(slices):
                slices = [slices]

            self.slices = slices
        else:
            raise StandardError('\'slices\' must be either single, tuple, or list of slice or int objects')

    def __iter__(self):
        return self.slices.__iter__()

    def __len__(self):
        return len(self.slices)

def is_valid_constraint(v):
    ret = False
    if isinstance(v, (slice, int)) or\
       (isinstance(v, (list,tuple)) and np.array([is_valid_constraint(e) for e in v]).all()):
        ret = True

    return ret

def get_valid_DomainOfApplication(v, valid_shape):
    """
    Takes the value to validate and a tuple representing the valid_shape
    """

    if v is None:
        if len(valid_shape) == 1:
            v = slice(None)
        else:
            v = [slice(None) for x in valid_shape]

    if not isinstance(v, DomainOfApplication):
        v = DomainOfApplication(v)

    return v

class BaseEnum(object):

    @classmethod
    def is_member(cls, value, want):
        return hasattr(cls, value) and value == want

    @classmethod
    def has_member(cls, value):
        return hasattr(cls, value)


class AxisTypeEnum(BaseEnum):
    """
    Enumeration of Axis Types used when building CRS objects and assigning the ParameterContext.reference_frame

    Temporarily taken from: http://www.unidata.ucar.edu/software/netcdf-java/v4.2/javadoc/ucar/nc2/constants/AxisType.html
    """
    # Ensemble represents the ensemble coordinate
    ENSEMBLE = 'ENSEMBLE'

    # GeoX represents a x coordinate
    GEO_X = 'GEO_X'

    # GeoY represents a y coordinate
    GEO_Y = 'GEO_Y'

    # GeoZ represents a z coordinate
    GEO_Z = 'GEO_Z'

    # Height represents a vertical height coordinate
    HEIGHT = 'HEIGHT'

    # Lat represents a latitude coordinate
    LAT = 'LAT'

    # Lon represents a longitude coordinate
    LON = 'LON'

    # Pressure represents a vertical pressure coordinate
    PRESSURE = 'PRESSURE'

    # RadialAzimuth represents a radial azimuth coordinate
    RADIAL_AZIMUTH = 'RADIAL_AZIMUTH'

    # RadialDistance represents a radial distance coordinate
    RADIAL_DISTANCE = 'RADIAL_DISTANCE'

    # RadialElevation represents a radial elevation coordinate
    RADIAL_ELEVATION = 'RADIAL_ELEVATION'

    # RunTime represents the runTime coordinate
    RUNTIME = 'RUNTIME'

    # Time represents the time coordinate
    TIME = 'TIME'

class MutabilityEnum(BaseEnum):
    """
    Enumeration of mutability types used in creation of concrete AbstractDomain objects
    """
    # NTK: mutable indicates ...

    ## Indicates the domain cannot be changed
    IMMUTABLE = 'IMMUTABLE'
    ## Indicates the domain can be expanded in any of it's dimensions
    EXTENSIBLE = 'EXTENSIBLE'
    ## NTK: Indicates ...
    MUTABLE = 'MUTABLE'

class VariabilityEnum(BaseEnum):
    """
    Enumeration of Variability used when building ParameterContext objects
    """
    ## Indicates that the associated object is variable temporally, but not spatially
    TEMPORAL = 'TEMPORAL'
    ## Indicates that the associated object is variable spatially, but not temporally
    SPATIAL = 'SPATIAL'
    ## Indicates that the associated object is variable both temporally and spatially
    BOTH = 'BOTH'
    ## Indicates that the associated object has NO variability; is constant in both space and time
    NONE = 'NONE'
