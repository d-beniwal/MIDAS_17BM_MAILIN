from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import defaults

# Define the base class for declarative class definitions
Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    user_id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(120), nullable=False)
    name = Column(String(120))
    email = Column(String(120))
    orcid = Column(String(19))
    mailing_address = Column(String(200))
    role = Column(String(19))
    badge = Column(Integer)

    def __repr__(self):
        return f'<User {self.username}>'

class Sample(Base):
    __tablename__ = 'sample'
    sample_id = Column(Integer, primary_key=True)
    proposal_id = Column(Integer, ForeignKey('proposal.proposal_id'))
    ESAF_number = Column(Integer)
    chemical_formula = Column(String(255))
    chemical_name = Column(String(255))
    sample_name = Column(String(255))
    safety_codes = Column(String(255))
    safety_text = Column(String(255))
    status = Column(Integer)

class SampleUser(Base):
    __tablename__ = 'sample__user'
    sample__user_id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey('sample.sample_id'))
    user_id = Column(Integer, ForeignKey('user.user_id'))

    sample = relationship('Sample', backref='sample__users')
    user = relationship('User', backref='sample__users')
    
class ScanRequest(Base):
    __tablename__ = 'scan_request'
    scan_request_id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey('sample.sample_id'))
    beamline = Column(String(255))
    status = Column(Integer)
    scan_params_id = Column(Integer)

class ScanParams_11BM(Base):
    __tablename__ = 'scan_params_11bm'
    params_id = Column(Integer, primary_key=True)
    start_angle = Column(Float)
    end_angle = Column(Float)
    step_size = Column(Float)
    count_time = Column(Float)
    collection_temp = Column(Float)
    default_option = Column(Integer)
    name = Column(String(255))
    
class ScanParams_17BM(Base):
    __tablename__ = 'scan_params_17bm'
    params_id = Column(Integer, primary_key=True)
    distance = Column(Float)
    energy = Column(Float)
    default_option = Column(Integer)
    name = Column(String(255))
    
class ScanParams_11IDB(Base):
    __tablename__ = 'scan_params_11idb'
    params_id = Column(Integer, primary_key=True)
    distance = Column(Float)
    energy = Column(Float)
    default_option = Column(Integer)
    name = Column(String(255))
     
class ScanData(Base):
    __tablename__ = 'scan_data'
    scan_data_id = Column(Integer, primary_key=True)
    scan_request_id = Column(Integer, ForeignKey('scan_request.scan_request_id'))    
    filename = Column(String(255))
    datatype = Column(String(255))
    location = Column(String(255))
    locationtype = Column(String(255))
    
class Cartridge(Base):
    __tablename__ = 'cartridge'
    cartridge_id = Column(Integer, primary_key=True)
    cartridge_type = Column(String(120), nullable=False)
    proposal_request_id = Column(Integer, ForeignKey('proposal_request.proposal_request_id'), nullable=False)
    barcode = Column(String(255), nullable=False)
    size = Column(Integer)
    primary = Column(Integer)
    
    proposal_request = relationship('ProposalRequest', backref='cartridges')

    known_types = defaults.known_types
    default_sizes = defaults.default_sizes
    
    def get_type_name(self):
        """Returns a readable name for the cartridge type."""
        return self.known_types.get(self.cartridge_type, self.cartridge_type)

class SampleCartridge(Base):
    __tablename__ = 'sample__cartridge'
    sample__cartridge_id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey('sample.sample_id'))
    cartridge_id = Column(Integer, ForeignKey('cartridge.cartridge_id'))
    position = Column(Integer)
    position_text = Column(String(120))

    sample = relationship('Sample', backref='sample__cartridge')
    cartridge = relationship('Cartridge', backref='sample__cartridge')

class Proposal(Base):
    __tablename__ = 'proposal'
    proposal_id = Column(Integer, primary_key=True)
    beamline = Column(String(19))
    proposal_number = Column(Integer)
    title = Column(String(200))
    allowance = Column(Integer)
    claimed = Column(Integer)

    cartridge_types = defaults.cartridge_types

    def beamline_name(self):
        import re
        match = re.match(r"(\d+)([a-zA-Z]+)", self.beamline)
        if match:
            number_part, char_part = match.groups()
            return f"{number_part}-{char_part.upper()}"
        return self.beamline

    def add_claimed(self, amt):
        self.claimed += amt
        session.commit()

class ProposalRequest(Base):
    __tablename__ = 'proposal_request'
    proposal_request_id = Column(Integer, primary_key=True)
    proposal_id = Column(Integer, ForeignKey('proposal.proposal_id'))
    type = Column(String(19))
    number = Column(Integer)
    filled = Column(Integer)
    user_id = Column(Integer, ForeignKey('user.user_id'))

    def get_type_name(self):
        type_names = Cartridge.known_types
        return type_names.get(self.type, self.type)

    def default_size(self):
        size_map = Cartridge.default_sizes
        return size_map.get(self.type, 0)

class ProposalUser(Base):
    __tablename__ = 'proposal__user'
    proposal__user_id = Column(Integer, primary_key=True)
    proposal_id = Column(Integer, ForeignKey('proposal.proposal_id'))
    user_id = Column(Integer, ForeignKey('user.user_id'))

    proposal = relationship('Proposal', backref='proposal__users')
    user = relationship('User', backref='proposal__users')
    
class ESAFCounter(Base):
    __tablename__ = 'esaf_counters'
    esaf_id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    counter = Column(Integer, nullable=False)
    beamline = Column(String(19), nullable=False)


