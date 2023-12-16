from datetime import datetime

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String,
                        Table, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

dataset_tag_association = Table(
    'dataset_tag', Base.metadata,
    Column('dataset_id', Integer, ForeignKey('datasets.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True))


class Experiment(Base):
    __tablename__ = 'experiments'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, default=datetime.utcnow)
    researcher_id = Column(Integer, ForeignKey('researchers.id'))
    datasets = relationship('Dataset', back_populates='experiment')


class Researcher(Base):
    __tablename__ = 'researchers'
    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    affiliation = Column(String)
    experiments = relationship('Experiment', back_populates='researcher')


class Dataset(Base):
    __tablename__ = 'datasets'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    tags = relationship('Tag',
                        secondary=dataset_tag_association,
                        back_populates='datasets')
    creation_date = Column(DateTime, default=datetime.utcnow)
    modification_date = Column(DateTime, default=datetime.utcnow)
    experiment_id = Column(Integer, ForeignKey('experiments.id'))
    experiment = relationship('Experiment', back_populates='datasets')
    data_entries = relationship('DataEntry', back_populates='dataset')


class DataEntry(Base):
    __tablename__ = 'data_entries'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    value = Column(Float)
    units = Column(String)
    variable_name = Column(String)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    dataset = relationship('Dataset', back_populates='data_entries')


class Variable(Base):
    __tablename__ = 'variables'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    data_type = Column(String)


class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    datasets = relationship('Dataset',
                            secondary=dataset_tag_association,
                            back_populates='tags')


# 创建数据库引擎
engine = create_engine('sqlite:///experiment_data.db')

# 创建表
Base.metadata.create_all(engine)

# 创建会话
Session = sessionmaker(bind=engine)
session = Session()
